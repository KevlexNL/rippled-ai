import asyncio
import imaplib
import secrets
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors.shared.credentials_utils import (
    decrypt_credentials,
    encrypt_credentials,
)
from app.core.config import get_settings
from app.core.dependencies import get_current_user_id
from app.db.deps import get_db
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.orm import Source, User
from app.models.schemas import (
    EmailSetupRequest,
    MeetingSetupRequest,
    SlackSetupRequest,
    SlackTestRequest,
    SourceCreate,
    SourceRead,
    SourceUpdate,
)

router = APIRouter(prefix="/sources", tags=["sources"])


async def _ensure_user_exists(user_id: str, db: AsyncSession, email: str = "") -> None:
    """Auto-provision a user row on first API call.

    Supabase creates records in auth.users on signup, but our app's users
    table needs a corresponding row (FK constraint). This upserts it silently.

    When a real email is known (e.g. email setup flow) we update the row so
    the stored address stays current.  When no email is available we only
    insert if the row doesn't already exist — ON CONFLICT DO NOTHING avoids
    the SQLAlchemy/Postgres error caused by an empty SET clause.
    """
    if email:
        stmt = pg_insert(User).values(
            id=user_id,
            email=email,
        ).on_conflict_do_update(
            index_elements=["id"],
            set_={"email": email},
        )
    else:
        stmt = pg_insert(User).values(
            id=user_id,
            email=f"user_{user_id[:8]}@rippled.internal",
        ).on_conflict_do_nothing()
    await db.execute(stmt)
    await db.flush()




def _imap_connect_test(
    host: str, port: int, ssl: bool, email: str, password: str
) -> tuple[bool, str]:
    """Sync IMAP connection test. Returns (success, message)."""
    try:
        if ssl:
            conn = imaplib.IMAP4_SSL(host, port)
        else:
            conn = imaplib.IMAP4(host, port)
        conn.login(email, password)
        _, data = conn.select("INBOX", readonly=True)
        count = len(conn.search(None, "ALL")[1][0].split()) if data else 0
        conn.logout()
        return True, f"Connected to {email} — {count} messages in INBOX"
    except imaplib.IMAP4.error as e:
        return False, str(e)
    except Exception as e:
        return False, str(e)


def _to_schema(row: Source) -> SourceRead:
    return SourceRead(
        id=row.id,
        user_id=row.user_id,
        source_type=row.source_type,
        provider_account_id=row.provider_account_id,
        display_name=row.display_name,
        is_active=row.is_active,
        has_credentials=bool(row.credentials),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


# ---------------------------------------------------------------------------
# Test endpoints (must appear before /{source_id})
# ---------------------------------------------------------------------------


@router.post("/test/email")
async def test_email_connection(
    body: EmailSetupRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Test IMAP connection without persisting anything."""
    success, message = await asyncio.to_thread(
        _imap_connect_test,
        body.imap_host,
        body.imap_port,
        body.imap_ssl,
        body.email,
        body.app_password,
    )
    if success:
        return {"success": True, "message": message}
    return {"success": False, "error": message}


@router.post("/test/slack")
async def test_slack_token(
    body: SlackTestRequest,
    user_id: str = Depends(get_current_user_id),
) -> dict:
    """Validate a Slack bot token via auth.test."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {body.bot_token}"},
            )
        data = resp.json()
        if data.get("ok"):
            return {
                "success": True,
                "workspace": data.get("team"),
                "bot_user": data.get("user"),
            }
        return {"success": False, "error": data.get("error", "Invalid token")}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Onboarding status (must appear before /{source_id})
# ---------------------------------------------------------------------------


@router.get("/onboarding-status")
async def get_onboarding_status(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await _ensure_user_exists(user_id, db)
    result = await db.execute(
        select(Source).where(Source.user_id == user_id, Source.is_active.is_(True))
    )
    active_sources = result.scalars().all()
    return {
        "has_sources": len(active_sources) > 0,
        "sources": [
            {
                "source_type": s.source_type,
                "display_name": s.display_name,
                "is_active": s.is_active,
            }
            for s in active_sources
        ],
    }


# ---------------------------------------------------------------------------
# Setup endpoints (must appear before /{source_id})
# ---------------------------------------------------------------------------


@router.post("/setup/email", response_model=SourceRead)
async def setup_email_source(
    body: EmailSetupRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SourceRead:
    # Test connection first
    success, message = await asyncio.to_thread(
        _imap_connect_test,
        body.imap_host,
        body.imap_port,
        body.imap_ssl,
        body.email,
        body.app_password,
    )
    if not success:
        raise HTTPException(status_code=422, detail=f"IMAP connection failed: {message}")

    await _ensure_user_exists(user_id, db, email=body.email)
    credentials = encrypt_credentials(
        {
            "imap_host": body.imap_host,
            "imap_port": body.imap_port,
            "imap_ssl": body.imap_ssl,
            "imap_sent_folder": body.imap_sent_folder,
            "imap_password": body.app_password,
            "imap_user": body.email,
            "internal_domains": body.internal_domains,
        }
    )

    # Upsert: find existing email source for this user
    result = await db.execute(
        select(Source).where(
            Source.user_id == user_id,
            Source.source_type == "email",
        )
    )
    source = result.scalar_one_or_none()

    if source is None:
        source = Source(user_id=user_id, source_type="email")
        db.add(source)

    source.provider_account_id = body.email
    source.display_name = body.email
    source.is_active = True
    source.credentials = credentials
    source.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(source)
    return _to_schema(source)


@router.post("/setup/slack", response_model=SourceRead)
async def setup_slack_source(
    body: SlackSetupRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SourceRead:
    # Validate token
    team_id = None
    workspace_name = None
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {body.bot_token}"},
            )
        data = resp.json()
        if not data.get("ok"):
            raise HTTPException(
                status_code=422,
                detail=f"Slack token validation failed: {data.get('error', 'unknown')}",
            )
        team_id = data.get("team_id")
        workspace_name = data.get("team")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=422, detail=f"Failed to validate Slack token: {exc}"
        )

    credentials = encrypt_credentials(
        {
            "bot_token": body.bot_token,
            "signing_secret": body.signing_secret,
            "slack_user_id": body.slack_user_id,
            "team_id": team_id,
        }
    )

    await _ensure_user_exists(user_id, db)
    # Upsert: find existing slack source for this user
    result = await db.execute(
        select(Source).where(
            Source.user_id == user_id,
            Source.source_type == "slack",
        )
    )
    source = result.scalar_one_or_none()

    if source is None:
        source = Source(user_id=user_id, source_type="slack")
        db.add(source)

    source.provider_account_id = team_id
    source.display_name = workspace_name
    source.is_active = True
    source.credentials = credentials
    source.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(source)
    return _to_schema(source)


@router.post("/setup/meeting")
async def setup_meeting_source(
    body: MeetingSetupRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    settings = get_settings()
    webhook_url = f"{settings.base_url}{settings.api_prefix}/webhooks/meeting/events"

    await _ensure_user_exists(user_id, db)
    # Upsert: find existing meeting source for this user + platform
    result = await db.execute(
        select(Source).where(
            Source.user_id == user_id,
            Source.source_type == "meeting",
            Source.provider_account_id == body.platform,
        )
    )
    source = result.scalar_one_or_none()
    is_new = source is None

    if is_new:
        webhook_secret = secrets.token_urlsafe(32)
        source = Source(user_id=user_id, source_type="meeting")
        db.add(source)
    else:
        # Preserve the existing secret; do not regenerate on update
        existing_creds = decrypt_credentials(source.credentials or {})
        webhook_secret = existing_creds.get("webhook_secret")

    source.provider_account_id = body.platform
    source.display_name = body.display_name or body.platform
    source.is_active = True
    source.credentials = encrypt_credentials(
        {"webhook_secret": webhook_secret} if webhook_secret else {}
    )
    source.metadata_ = {"platform": body.platform}
    source.updated_at = datetime.now(timezone.utc)

    await db.flush()
    await db.refresh(source)
    return {
        "source": _to_schema(source),
        "webhook_url": webhook_url,
        # Only expose the secret on creation; on update it's null (use regenerate-secret)
        "webhook_secret": webhook_secret if is_new else None,
    }


# ---------------------------------------------------------------------------
# Regenerate meeting webhook secret (must appear before /{source_id})
# ---------------------------------------------------------------------------


@router.post("/{source_id}/regenerate-secret")
async def regenerate_meeting_secret(
    source_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(
        select(Source).where(Source.id == source_id, Source.user_id == user_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if source.source_type != "meeting":
        raise HTTPException(
            status_code=422, detail="Secret regeneration only valid for meeting sources"
        )

    new_secret = secrets.token_urlsafe(32)
    existing = decrypt_credentials(source.credentials) if source.credentials else {}
    existing["webhook_secret"] = new_secret
    source.credentials = encrypt_credentials(existing)
    source.updated_at = datetime.now(timezone.utc)

    await db.flush()
    return {"webhook_secret": new_secret}


# ---------------------------------------------------------------------------
# Standard CRUD routes
# ---------------------------------------------------------------------------


@router.post("", response_model=SourceRead, status_code=201)
async def create_source(
    body: SourceCreate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SourceRead:
    source = Source(
        user_id=user_id,
        source_type=body.source_type,
        provider_account_id=body.provider_account_id,
        display_name=body.display_name,
        metadata_=body.metadata_,
        credentials=encrypt_credentials(body.credentials) if body.credentials else None,
    )
    db.add(source)
    await db.flush()
    await db.refresh(source)
    return _to_schema(source)


@router.get("", response_model=list[SourceRead])
async def list_sources(
    limit: int = 5,
    offset: int = 0,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[SourceRead]:
    if limit > 200:
        limit = 200
    result = await db.execute(
        select(Source)
        .where(Source.user_id == user_id)
        .order_by(Source.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [_to_schema(row) for row in result.scalars()]


@router.get("/{source_id}", response_model=SourceRead)
async def get_source(
    source_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SourceRead:
    result = await db.execute(
        select(Source).where(Source.id == source_id, Source.user_id == user_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    return _to_schema(source)


@router.patch("/{source_id}", response_model=SourceRead)
async def update_source(
    source_id: str,
    body: SourceUpdate,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SourceRead:
    result = await db.execute(
        select(Source).where(Source.id == source_id, Source.user_id == user_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    if body.display_name is not None:
        source.display_name = body.display_name
    if body.is_active is not None:
        source.is_active = body.is_active
    if body.metadata_ is not None:
        source.metadata_ = body.metadata_
    if body.credentials is not None:
        source.credentials = encrypt_credentials(body.credentials)

    source.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(source)
    return _to_schema(source)


@router.delete("/{source_id}", status_code=204)
async def delete_source(
    source_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(
        select(Source).where(Source.id == source_id, Source.user_id == user_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    source.is_active = False
    source.updated_at = datetime.now(timezone.utc)
