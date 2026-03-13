import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.api.routes import sources, source_items, commitments, surface, candidates
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
    allow_origins=["*"],  # Tighten before production
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
app.include_router(surface.router, prefix=settings.api_prefix, tags=["surfacing"])
app.include_router(candidates.router, prefix=settings.api_prefix, tags=["candidates"])
app.include_router(webhook_email.router, prefix=settings.api_prefix, tags=["webhooks"])
app.include_router(webhook_slack.router, prefix=settings.api_prefix, tags=["webhooks"])
app.include_router(webhook_meetings.router, prefix=settings.api_prefix, tags=["webhooks"])

# Serve frontend SPA
_PUBLIC_DIR = os.path.join(os.path.dirname(__file__), "..", "api", "public")
if os.path.isdir(_PUBLIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(_PUBLIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        index = os.path.join(_PUBLIC_DIR, "index.html")
        return FileResponse(index)
