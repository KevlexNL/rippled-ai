import hmac
from fastapi import Header, HTTPException
from app.core.config import get_settings


async def verify_admin_key(x_admin_key: str = Header(...)) -> None:
    settings = get_settings()
    if not settings.admin_secret_key:
        raise HTTPException(status_code=503, detail="Admin API not configured")
    if not hmac.compare_digest(x_admin_key, settings.admin_secret_key):
        raise HTTPException(status_code=401, detail="Invalid admin key")
