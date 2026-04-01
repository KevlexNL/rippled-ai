"""Debug pipeline API — dry-run the orchestration pipeline on raw text.

Endpoint:
    POST /debug/pipeline — run text through extraction/classification stages
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from app.connectors.shared.normalized_signal import NormalizedSignal
from app.services.orchestration.orchestrator import SignalOrchestrator

router = APIRouter(prefix="/debug", tags=["debug"])


class DebugPipelineRequest(BaseModel):
    text: str = Field(..., min_length=1)
    source_type: str = "email"
    subject: str | None = None

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("text must not be blank")
        return v


@router.post("/pipeline")
def run_debug_pipeline(body: DebugPipelineRequest) -> dict:
    """Run the orchestration pipeline on raw text without persisting.

    Accepts a text payload and returns per-stage extraction output
    for golden-dataset validation of speech-act classification,
    commitment extraction, and entity extraction.
    """
    now = datetime.now(tz=timezone.utc)
    signal = NormalizedSignal(
        signal_id=f"debug-{uuid.uuid4()}",
        source_type=body.source_type,
        occurred_at=now,
        authored_at=now,
        latest_authored_text=body.text,
        subject=body.subject,
    )

    orchestrator = SignalOrchestrator(db=None, dry_run=True)
    result = orchestrator.process(signal)

    return result.model_dump()
