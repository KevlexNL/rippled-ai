from fastapi import Header, HTTPException


async def get_current_user_id(x_user_id: str = Header(...)) -> str:
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header required")
    return x_user_id
