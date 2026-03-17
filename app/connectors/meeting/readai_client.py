"""Read.ai API client with OAuth token refresh.

Handles authentication, pagination, and meeting detail expansion.
"""
import base64
import logging

import httpx

logger = logging.getLogger(__name__)

READAI_AUTH_URL = "https://authn.read.ai/oauth2/token"
READAI_API_BASE = "https://api.read.ai/v1"


class ReadAIAuthError(Exception):
    """Raised when Read.ai OAuth token refresh fails."""


class ReadAIClient:
    """Synchronous Read.ai API client."""

    def __init__(
        self,
        access_token: str,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.client_id = client_id
        self.client_secret = client_secret

    def refresh_access_token(self) -> None:
        """Refresh the OAuth access token using the refresh token."""
        creds = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()

        resp = httpx.post(
            READAI_AUTH_URL,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {creds}",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            },
        )

        if resp.status_code != 200:
            raise ReadAIAuthError(
                f"Token refresh failed: {resp.status_code} — {resp.text}"
            )

        data = resp.json()
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
        logger.info("Read.ai: token refreshed successfully")

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"}

    def _get_with_retry(self, url: str, params: dict | None = None) -> httpx.Response:
        """GET with one retry on 401 (token refresh)."""
        resp = httpx.get(url, headers=self._auth_headers(), params=params)
        if resp.status_code == 401:
            logger.info("Read.ai: 401 received, refreshing token and retrying")
            self.refresh_access_token()
            resp = httpx.get(url, headers=self._auth_headers(), params=params)
        return resp

    def list_meetings(self, since_ms: int, limit: int = 10) -> list[dict]:
        """Fetch all meetings since a timestamp, paginating through results."""
        meetings: list[dict] = []
        cursor: str | None = None

        while True:
            params: dict = {
                "limit": limit,
                "start_time_ms.gte": since_ms,
            }
            if cursor:
                params["cursor"] = cursor

            resp = self._get_with_retry(f"{READAI_API_BASE}/meetings", params=params)
            if resp.status_code != 200:
                logger.error("Read.ai list_meetings failed: %s — %s", resp.status_code, resp.text)
                break

            data = resp.json()
            meetings.extend(data.get("meetings", []))

            cursor = data.get("next_cursor")
            if not cursor:
                break

        return meetings

    def get_meeting_detail(self, meeting_id: str) -> dict:
        """Fetch meeting details with expanded summary, action_items, transcript."""
        params = {
            "expand[]": ["summary", "action_items", "transcript"],
        }
        resp = self._get_with_retry(
            f"{READAI_API_BASE}/meetings/{meeting_id}",
            params=params,
        )
        if resp.status_code != 200:
            logger.error(
                "Read.ai get_meeting_detail(%s) failed: %s — %s",
                meeting_id, resp.status_code, resp.text,
            )
            return {}
        return resp.json()
