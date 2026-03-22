"""Replay runner — reprocess stored raw signals through the current normalization pipeline.

Implements WO Deliverable C: Replay/debug support for normalization.
Loads RawSignalIngest records from the DB and runs them through the
current EmailNormalizationService to validate normalization behavior.
"""

import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.email.schemas import RawEmailPayload
from app.connectors.shared.normalized_signal import NormalizedSignal
from app.models.orm import RawSignalIngest
from app.services.normalization.email_normalization_service import EmailNormalizationService

logger = logging.getLogger(__name__)


class ReplayResult:
    """Result of replaying a single raw signal."""

    __slots__ = ("raw_ingest_id", "signal", "error", "duration_ms")

    def __init__(
        self,
        raw_ingest_id: str,
        signal: NormalizedSignal | None = None,
        error: str | None = None,
        duration_ms: float = 0.0,
    ):
        self.raw_ingest_id = raw_ingest_id
        self.signal = signal
        self.error = error
        self.duration_ms = duration_ms

    @property
    def success(self) -> bool:
        return self.signal is not None and self.error is None


class ReplayRunner:
    """Reprocess stored raw signals through the normalization pipeline."""

    def __init__(self, db: Session, user_email: str):
        self._db = db
        self._user_email = user_email
        self._service = EmailNormalizationService(user_email=user_email)

    def replay_all(self, limit: int = 100) -> list[ReplayResult]:
        """Replay all raw signal ingests (up to limit)."""
        rows = self._db.execute(
            select(RawSignalIngest)
            .where(RawSignalIngest.source_type == "email")
            .order_by(RawSignalIngest.ingested_at.desc())
            .limit(limit)
        ).scalars().all()

        results = []
        for row in rows:
            results.append(self._replay_one(row))

        return results

    def replay_by_id(self, ingest_id: str) -> ReplayResult:
        """Replay a single raw signal ingest by ID."""
        row = self._db.get(RawSignalIngest, ingest_id)
        if not row:
            return ReplayResult(
                raw_ingest_id=ingest_id,
                error=f"RawSignalIngest {ingest_id} not found",
            )
        return self._replay_one(row)

    def _replay_one(self, row: RawSignalIngest) -> ReplayResult:
        """Replay a single raw ingest through the pipeline."""
        start = time.monotonic()
        try:
            payload = RawEmailPayload(**row.payload_json)
            signal = self._service.normalize(payload)
            duration = (time.monotonic() - start) * 1000

            logger.info(
                "Replay OK: ingest=%s provider_msg=%s duration=%.1fms flags=%s",
                row.id,
                row.provider_message_id,
                duration,
                [f.value for f in signal.normalization_flags],
            )

            return ReplayResult(
                raw_ingest_id=row.id,
                signal=signal,
                duration_ms=duration,
            )

        except Exception as exc:
            duration = (time.monotonic() - start) * 1000
            logger.error(
                "Replay FAILED: ingest=%s error=%s duration=%.1fms",
                row.id,
                str(exc),
                duration,
            )
            return ReplayResult(
                raw_ingest_id=row.id,
                error=str(exc),
                duration_ms=duration,
            )
