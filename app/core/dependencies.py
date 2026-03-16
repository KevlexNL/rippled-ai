from fastapi import Header, HTTPException, Query


async def get_current_user_id(x_user_id: str = Header(...)) -> str:
    if not x_user_id:
        raise HTTPException(status_code=400, detail="X-User-ID header required")
    return x_user_id


async def get_user_id_for_redirect(
    user_id: str | None = Query(None),
    x_user_id: str | None = Header(None),
) -> str:
    """Resolve user ID from query param (browser navigations) or header.

    OAuth start endpoints are opened via browser navigation (<a href> /
    window.location.href) which cannot carry custom HTTP headers.  The
    frontend therefore passes the user ID as a query parameter instead.
    """
    resolved = user_id or x_user_id
    if not resolved:
        raise HTTPException(
            status_code=400,
            detail="user_id query parameter or X-User-ID header required",
        )
    return resolved
