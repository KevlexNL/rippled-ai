import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.api.routes import sources, source_items, commitments, surface, candidates, digest as digest_routes
from app.api.routes import contexts as contexts_routes
from app.api.routes import events as events_routes, integrations as integrations_routes
from app.api.routes import admin as admin_routes
from app.api.routes import user_settings as user_settings_routes
from app.api.routes import clarifications as clarifications_routes
from app.api.routes import stats as stats_routes
from app.api.routes.webhooks import email as webhook_email, slack as webhook_slack, meetings as webhook_meetings

settings = get_settings()

app = FastAPI(
    title="Rippled AI",
    description="Commitment intelligence engine — observes communication, surfaces what matters.",
    version="0.1.0",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.app_env}


app.include_router(sources.router, prefix=settings.api_prefix, tags=["sources"])
app.include_router(source_items.router, prefix=settings.api_prefix, tags=["ingestion"])
app.include_router(commitments.router, prefix=settings.api_prefix, tags=["commitments"])
app.include_router(contexts_routes.router, prefix=settings.api_prefix, tags=["contexts"])
app.include_router(surface.router, prefix=settings.api_prefix, tags=["surfacing"])
app.include_router(candidates.router, prefix=settings.api_prefix, tags=["candidates"])
app.include_router(webhook_email.router, prefix=settings.api_prefix, tags=["webhooks"])
app.include_router(webhook_slack.router, prefix=settings.api_prefix, tags=["webhooks"])
app.include_router(webhook_meetings.router, prefix=settings.api_prefix, tags=["webhooks"])
app.include_router(digest_routes.router, prefix=settings.api_prefix, tags=["digest"])
app.include_router(events_routes.router, prefix=settings.api_prefix, tags=["events"])
app.include_router(integrations_routes.router, prefix=settings.api_prefix, tags=["integrations"])
app.include_router(admin_routes.router, prefix=settings.api_prefix, tags=["admin"])
app.include_router(user_settings_routes.router, prefix=settings.api_prefix, tags=["user-settings"])
app.include_router(clarifications_routes.router, prefix=settings.api_prefix, tags=["clarifications"])
app.include_router(stats_routes.router, prefix=settings.api_prefix, tags=["stats"])

# Serve user frontend SPA
_PUBLIC_DIR = os.path.join(os.path.dirname(__file__), "..", "api", "public")

# Serve admin frontend SPA
# IMPORTANT: admin SPA fallback must precede user SPA catch-all
_ADMIN_PUBLIC_DIR = os.path.join(os.path.dirname(__file__), "..", "api", "public-admin")
if os.path.isdir(_ADMIN_PUBLIC_DIR):
    _admin_assets = os.path.join(_ADMIN_PUBLIC_DIR, "assets")
    if os.path.isdir(_admin_assets):
        app.mount("/admin/assets", StaticFiles(directory=_admin_assets), name="admin-assets")

    @app.get("/admin", include_in_schema=False)
    @app.get("/admin/{full_path:path}", include_in_schema=False)
    async def admin_spa_fallback(full_path: str = "") -> FileResponse:
        index = os.path.join(_ADMIN_PUBLIC_DIR, "index.html")
        return FileResponse(index)

if os.path.isdir(_PUBLIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(_PUBLIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        index = os.path.join(_PUBLIC_DIR, "index.html")
        return FileResponse(index)
