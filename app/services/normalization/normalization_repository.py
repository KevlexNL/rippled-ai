"""NormalizationRepository — store and fetch raw ingests and normalized signals.

Implements WO service boundary: NormalizationRepository.
"""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.shared.normalized_signal import (
    NormalizedSignal,
)
from app.models.orm import NormalizationRun, NormalizedSignalORM, RawSignalIngest
from app.models.schemas import NormalizationRunCreate, RawSignalIngestCreate

logger = logging.getLogger(__name__)


class NormalizationRepository:
    """Persist and retrieve normalization pipeline entities."""

    def __init__(self, db: Session):
        self._db = db

    # --- RawSignalIngest ---

    def save_raw_ingest(self, ingest: RawSignalIngestCreate) -> RawSignalIngest:
        """Persist a RawSignalIngest record. Returns the ORM object."""
        row = RawSignalIngest(
            source_type=ingest.source_type,
            provider=ingest.provider,
            provider_message_id=ingest.provider_message_id,
            provider_thread_id=ingest.provider_thread_id,
            provider_account_id=ingest.provider_account_id,
            received_at=ingest.received_at,
            payload_json=ingest.payload_json,
            payload_hash=ingest.payload_hash,
            parse_status="pending",
        )
        self._db.add(row)
        self._db.flush()
        self._db.refresh(row)
        return row

    def find_raw_ingest_by_hash(self, payload_hash: str) -> RawSignalIngest | None:
        """Find existing ingest by payload hash (deduplication)."""
        return self._db.execute(
            select(RawSignalIngest).where(RawSignalIngest.payload_hash == payload_hash)
        ).scalar_one_or_none()

    def get_raw_ingest(self, ingest_id: str) -> RawSignalIngest | None:
        """Fetch a raw ingest by ID."""
        return self._db.get(RawSignalIngest, ingest_id)

    def update_parse_status(
        self,
        ingest_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        """Update parse_status on a RawSignalIngest."""
        row = self._db.get(RawSignalIngest, ingest_id)
        if row:
            row.parse_status = status
            row.parse_error = error
            self._db.flush()

    # --- NormalizedSignal ---

    def save_normalized_signal(
        self,
        signal: NormalizedSignal,
        raw_ingest_id: str,
    ) -> NormalizedSignalORM:
        """Persist a NormalizedSignal to the database."""
        row = NormalizedSignalORM(
            raw_signal_ingest_id=raw_ingest_id,
            source_type=signal.source_type,
            source_subtype=signal.source_subtype,
            provider=signal.provider or "email",
            provider_message_id=signal.provider_message_id or signal.signal_id,
            provider_thread_id=signal.provider_thread_id or signal.source_thread_id,
            provider_account_id=signal.provider_account_id,
            signal_timestamp=signal.signal_timestamp or signal.occurred_at,
            authored_at=signal.authored_at,
            direction=signal.direction.value if signal.direction else None,
            is_inbound=signal.is_inbound,
            is_outbound=signal.is_outbound,
            subject=signal.subject,
            latest_authored_text=signal.latest_authored_text,
            prior_context_text=signal.prior_context_text,
            full_visible_text=signal.full_visible_text,
            html_present=signal.html_present,
            text_present=signal.text_present,
            sender_json=signal.sender.model_dump() if signal.sender else None,
            to_json=[p.model_dump() for p in signal.to] if signal.to else None,
            cc_json=[p.model_dump() for p in signal.cc] if signal.cc else None,
            bcc_json=[p.model_dump() for p in signal.bcc] if signal.bcc else None,
            reply_to_json=[p.model_dump() for p in signal.reply_to] if signal.reply_to else None,
            participants_json=[p.model_dump() for p in signal.participants] if signal.participants else None,
            attachment_metadata_json=[a.model_dump() for a in signal.attachment_metadata] if signal.attachment_metadata else None,
            thread_position=signal.thread_position,
            message_index_guess=signal.message_index_guess,
            language_code=signal.language_code,
            normalization_version=signal.normalization_version,
            normalization_flags=[f.value for f in signal.normalization_flags] if signal.normalization_flags else None,
            normalization_warnings=signal.normalization_warnings if signal.normalization_warnings else None,
        )
        self._db.add(row)
        self._db.flush()
        self._db.refresh(row)
        return row

    def get_normalized_signal(self, signal_id: str) -> NormalizedSignalORM | None:
        """Fetch a normalized signal by ID."""
        return self._db.get(NormalizedSignalORM, signal_id)

    def find_by_provider_message_id(self, provider_message_id: str) -> NormalizedSignalORM | None:
        """Find normalized signal by provider message ID."""
        return self._db.execute(
            select(NormalizedSignalORM).where(
                NormalizedSignalORM.provider_message_id == provider_message_id
            )
        ).scalar_one_or_none()

    # --- NormalizationRun ---

    def save_normalization_run(self, run: NormalizationRunCreate) -> NormalizationRun:
        """Persist a NormalizationRun audit record."""
        row = NormalizationRun(
            normalized_signal_id=run.normalized_signal_id,
            normalization_version=run.normalization_version,
            status=run.status,
            warnings_json=run.warnings_json,
            timings_json=run.timings_json,
        )
        self._db.add(row)
        self._db.flush()
        self._db.refresh(row)
        return row
