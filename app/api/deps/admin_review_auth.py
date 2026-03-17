"""Admin review auth dependency.

Checks X-User-ID header and verifies the user is Kevin's hardcoded ID
or has is_super_admin=true in user_settings.
"""

from fastapi import Header, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.deps import get_db
from app.models.orm import UserSettings

ADMIN_USER_ID = "441f9c1f-9428-477e-a04f-fb8d5e654ec2"


async def verify_admin_reviewer(
    x_user_id: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> str:
    """Return user_id if the caller is an admin reviewer, else raise 403."""
    if x_user_id == ADMIN_USER_ID:
        return x_user_id

    result = await db.execute(
        select(UserSettings.is_super_admin).where(UserSettings.user_id == x_user_id)
    )
    row = result.scalar_one_or_none()
    if row is True:
        return x_user_id

    raise HTTPException(status_code=403, detail="Admin access required")
