"""EmailRawIngestService — accept raw email payload, validate, produce RawSignalIngestCreate.

Implements WO service boundary: EmailRawIngestService.
"""

import hashlib
import json

from app.connectors.email.schemas import RawEmailPayload
from app.models.enums import SourceType
from app.models.schemas import RawSignalIngestCreate


class EmailRawIngestService:
    """Accept raw email payloads and produce RawSignalIngestCreate records."""

    def create_ingest(
        self,
        payload: RawEmailPayload,
        provider: str,
        provider_account_id: str | None = None,
    ) -> RawSignalIngestCreate:
        """Convert a RawEmailPayload into a RawSignalIngestCreate.

        Computes a deterministic SHA256 hash of the payload for deduplication.
        """
        payload_dict = payload.model_dump(mode="json")
        payload_json_str = json.dumps(payload_dict, sort_keys=True, default=str)
        payload_hash = hashlib.sha256(payload_json_str.encode()).hexdigest()

        # Extract thread ID from references or in_reply_to
        thread_id = _extract_thread_id(
            payload.message_id, payload.in_reply_to, payload.references
        )

        return RawSignalIngestCreate(
            source_type=SourceType.email,
            provider=provider,
            provider_message_id=payload.message_id,
            provider_thread_id=thread_id,
            provider_account_id=provider_account_id,
            received_at=payload.date,
            payload_json=payload_dict,
            payload_hash=payload_hash,
        )


def _extract_thread_id(
    message_id: str,
    in_reply_to: str | None,
    references: str | None,
) -> str:
    """Extract the root message ID to use as thread_id.

    Prefers the oldest reference (first in References header) or in_reply_to.
    Falls back to message_id itself (top-level message).
    """
    if references:
        refs = references.strip().split()
        if refs:
            return refs[0]

    if in_reply_to:
        return in_reply_to.strip()

    return message_id
