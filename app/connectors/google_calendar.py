"""Google Calendar connector — Phase C3.

Syncs events from Google Calendar API into the local Event table.
Handles token refresh, cancellations, and rescheduling.

Public API:
    GoogleCalendarConnector(settings, db).sync(user_id) -> dict
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Sync window: fetch events from now to now + 30 days
_SYNC_WINDOW_DAYS = 30


class GoogleCalendarConnector:
    """Syncs Google Calendar events for a user into the local events table."""

    def __init__(self, settings=None, db=None):
        self._settings = settings
        self._db = db

    def sync(self, user_id: str) -> dict:
        """Sync events for the given user.

        Flow:
          1. Load UserSettings for user_id
          2. If no tokens → skip
          3. If token expired → refresh
          4. Fetch events from Google Calendar API
          5. Upsert Event rows by external_id
          6. Handle cancellations and rescheduling

        Returns:
            Dict with 'synced', 'created', 'updated', 'cancelled' counts.
        """
        from sqlalchemy import select
        from app.models.orm import UserSettings
        from app.connectors.shared.credentials_utils import decrypt_value, encrypt_value

        db = self._db
        settings = self._settings

        if not getattr(settings, "google_calendar_enabled", False):
            return {"status": "skipped", "reason": "google_calendar_enabled=false"}

        if not getattr(settings, "google_oauth_client_id", ""):
            return {"status": "skipped", "reason": "oauth not configured"}

        user_settings = db.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        ).scalar_one_or_none()

        if not user_settings or not user_settings.google_refresh_token:
            return {"status": "skipped", "reason": "user not authenticated"}

        access_token = decrypt_value(user_settings.google_access_token)
        refresh_token = decrypt_value(user_settings.google_refresh_token)
        token_expiry = user_settings.google_token_expiry

        # Refresh token if expired or missing
        if not access_token or (token_expiry and _is_expired(token_expiry)):
            credentials = self._refresh_access_token(refresh_token, settings)
            if credentials is None:
                return {"status": "error", "reason": "token refresh failed"}
            access_token = credentials["access_token"]
            user_settings.google_access_token = encrypt_value(access_token)
            if credentials.get("expiry"):
                user_settings.google_token_expiry = credentials["expiry"]
            db.flush()

        # Fetch events from Google Calendar
        try:
            raw_events = self._fetch_events(access_token, settings)
        except Exception as exc:
            logger.error("Google Calendar sync failed for user %s: %s", user_id, exc)
            return {"status": "error", "reason": str(exc)}

        # Upsert events
        created = 0
        updated = 0
        cancelled = 0

        for raw_event in raw_events:
            result = self._upsert_event(raw_event, db)
            if result == "created":
                created += 1
            elif result == "updated":
                updated += 1
            elif result == "cancelled":
                cancelled += 1

        db.flush()

        logger.info(
            "GoogleCalendarConnector.sync: user=%s created=%d updated=%d cancelled=%d",
            user_id, created, updated, cancelled,
        )

        return {
            "status": "synced",
            "created": created,
            "updated": updated,
            "cancelled": cancelled,
            "synced": created + updated + cancelled,
        }

    def _refresh_access_token(self, refresh_token: str, settings) -> dict | None:
        """Refresh the OAuth access token using google-auth-oauthlib."""
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request

            creds = Credentials(
                token=None,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=settings.google_oauth_client_id,
                client_secret=settings.google_oauth_client_secret,
            )
            creds.refresh(Request())
            expiry = creds.expiry
            if expiry and expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
            return {
                "access_token": creds.token,
                "expiry": expiry,
            }
        except Exception as exc:
            logger.error("Token refresh failed: %s", exc)
            return None

    def _fetch_events(self, access_token: str, settings) -> list[dict]:
        """Fetch upcoming events from Google Calendar API."""
        from googleapiclient.discovery import build
        from google.oauth2.credentials import Credentials

        creds = Credentials(token=access_token)
        service = build("calendar", "v3", credentials=creds)

        now = datetime.now(timezone.utc)
        time_max = now + timedelta(days=_SYNC_WINDOW_DAYS)

        result = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,  # expand recurring events
            orderBy="startTime",
            maxResults=250,
        ).execute()

        return result.get("items", [])

    def _upsert_event(self, raw: dict, db) -> str:
        """Upsert a single Google Calendar event. Returns 'created', 'updated', or 'cancelled'."""
        from sqlalchemy import select
        from app.models.orm import Event

        external_id = raw.get("id", "")
        status = raw.get("status", "confirmed")  # confirmed | cancelled | tentative

        existing = db.execute(
            select(Event).where(Event.external_id == external_id)
        ).scalar_one_or_none()

        starts_at = _parse_google_datetime(raw.get("start", {}))
        ends_at = _parse_google_datetime(raw.get("end", {}))
        title = raw.get("summary", "") or ""
        description = raw.get("description")
        location = raw.get("location")
        attendees_raw = raw.get("attendees", [])
        attendees = [
            {"email": a.get("email", ""), "name": a.get("displayName", ""), "response_status": a.get("responseStatus", "")}
            for a in attendees_raw
        ]
        recurrence = raw.get("recurrence")
        recurrence_rule = recurrence[0] if recurrence else None
        is_recurring = bool(raw.get("recurringEventId") or recurrence)

        now = datetime.now(timezone.utc)

        if existing is None:
            event = Event(
                id=str(uuid.uuid4()),
                external_id=external_id,
                title=title,
                description=description,
                starts_at=starts_at,
                ends_at=ends_at,
                is_recurring=is_recurring,
                recurrence_rule=recurrence_rule,
                event_type="explicit",
                status=status if status != "cancelled" else "cancelled",
                location=location,
                attendees=attendees if attendees else None,
                cancelled_at=now if status == "cancelled" else None,
            )
            db.add(event)
            return "cancelled" if status == "cancelled" else "created"
        else:
            old_status = existing.status

            if starts_at and existing.starts_at and _tz_aware(existing.starts_at) != _tz_aware(starts_at):
                existing.rescheduled_from = existing.starts_at
                existing.starts_at = starts_at

            if ends_at:
                existing.ends_at = ends_at

            existing.title = title
            existing.description = description
            existing.location = location
            existing.attendees = attendees if attendees else None
            existing.updated_at = now

            if old_status != "cancelled" and status == "cancelled":
                existing.status = "cancelled"
                existing.cancelled_at = now
                # Surface linked commitments (handled by surfacing sweep)
                return "cancelled"
            else:
                existing.status = status

            return "updated"


# ---------------------------------------------------------------------------
# OAuth helpers (used by the integrations API routes)
# ---------------------------------------------------------------------------

def get_auth_url(settings) -> str:
    """Return the Google OAuth consent URL."""
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        _client_config(settings),
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        redirect_uri=settings.google_oauth_redirect_uri,
    )
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    return auth_url


def exchange_code(code: str, settings) -> dict:
    """Exchange an OAuth authorization code for tokens.

    Returns dict with access_token, refresh_token, expiry.
    """
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        _client_config(settings),
        scopes=["https://www.googleapis.com/auth/calendar.readonly"],
        redirect_uri=settings.google_oauth_redirect_uri,
    )
    flow.fetch_token(code=code)
    creds = flow.credentials
    expiry = creds.expiry
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expiry": expiry,
    }


def revoke_token(access_token: str) -> None:
    """Revoke the Google OAuth access token."""
    import requests
    try:
        requests.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": access_token},
            timeout=5,
        )
    except Exception as exc:
        logger.warning("Token revocation failed: %s", exc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _client_config(settings) -> dict:
    return {
        "web": {
            "client_id": settings.google_oauth_client_id,
            "client_secret": settings.google_oauth_client_secret,
            "redirect_uris": [settings.google_oauth_redirect_uri],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def _parse_google_datetime(dt_obj: dict) -> datetime | None:
    """Parse Google Calendar dateTime or date into a timezone-aware datetime."""
    if not dt_obj:
        return None
    dt_str = dt_obj.get("dateTime") or dt_obj.get("date")
    if not dt_str:
        return None
    try:
        # Handle date-only (all-day events)
        if "T" not in dt_str:
            d = datetime.strptime(dt_str, "%Y-%m-%d")
            return d.replace(tzinfo=timezone.utc)
        # Handle datetime with timezone
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str).astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _is_expired(expiry: datetime) -> bool:
    """Return True if the token expiry is within 5 minutes."""
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry <= datetime.now(timezone.utc) + timedelta(minutes=5)


def _tz_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
