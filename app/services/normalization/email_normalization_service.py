"""EmailNormalizationService — parse raw email payload, extract bodies,
separate text, normalize participants/attachments, derive direction,
produce NormalizedSignal.

Implements WO service boundary: EmailNormalizationService.
Implements WO normalization rules 4.7.1 through 4.7.8.
"""

import uuid
from datetime import timezone

from app.connectors.email.schemas import RawEmailPayload
from app.connectors.shared.normalized_signal import (
    NormalizedAttachment,
    NormalizedSignal,
    Participant,
)
from app.models.enums import Direction, NormalizationFlag
from app.services.normalization.participant_resolver import ParticipantResolver
from app.services.normalization.quoted_text_parser import QuotedTextParser


class EmailNormalizationService:
    """Parse raw email payload into a canonical NormalizedSignal."""

    def __init__(self, user_email: str):
        self._user_email = user_email

    def normalize(self, payload: RawEmailPayload) -> NormalizedSignal:
        """Full normalization pipeline for a single email."""
        flags: list[NormalizationFlag] = []
        warnings: list[str] = []

        # 4.7.1 — Text extraction
        text_result = self._extract_text(payload, flags)

        # 4.7.4 — Direction detection
        all_recipient_emails = list(payload.to) + list(payload.cc)
        direction = ParticipantResolver.detect_direction(
            sender_email=payload.from_email,
            user_email=self._user_email,
            recipient_emails=all_recipient_emails,
        )

        # 4.7.5 — Participant normalization
        participants = ParticipantResolver.normalize_all(
            sender_email=payload.from_email,
            sender_name=payload.from_name,
            to_emails=list(payload.to),
            cc_emails=list(payload.cc),
            bcc_emails=[],  # BCC not visible in received headers
            reply_to_emails=[],
            user_email=self._user_email,
        )

        # 4.7.6 — Attachment metadata
        attachment_meta = self._extract_attachments(payload, flags)

        # 4.7.7 — Thread metadata
        thread_id = _extract_thread_id(
            payload.message_id, payload.in_reply_to, payload.references
        )

        # Source subtype detection
        source_subtype = _detect_subtype(payload)

        # Missing subject check
        if not payload.subject or not payload.subject.strip():
            flags.append(NormalizationFlag.missing_subject)

        # Normalize occurred_at to UTC
        occurred_at = payload.date
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)
        else:
            occurred_at = occurred_at.astimezone(timezone.utc)

        # Build legacy-compatible participants for backward compat
        actor = Participant(
            name=payload.from_name,
            email=payload.from_email,
            role="sender",
        )
        addressed = [
            Participant(email=e, role="recipient") for e in payload.to
        ] + [
            Participant(email=e, role="cc") for e in payload.cc
        ]

        return NormalizedSignal(
            # Legacy fields (backward compatible)
            signal_id=payload.message_id,
            source_type="email",
            source_thread_id=thread_id,
            source_message_id=payload.message_id,
            occurred_at=occurred_at,
            authored_at=occurred_at,
            actor_participants=[actor],
            addressed_participants=addressed,
            visible_participants=[actor] + addressed,
            latest_authored_text=text_result["latest_authored_text"],
            prior_context_text=text_result["prior_context_text"],
            metadata={"subject": payload.subject},
            # New WO fields
            id=str(uuid.uuid4()),
            source_subtype=source_subtype,
            provider="email",
            provider_message_id=payload.message_id,
            provider_thread_id=thread_id,
            provider_account_id=None,
            signal_timestamp=occurred_at,
            direction=direction,
            is_inbound=direction == Direction.inbound,
            is_outbound=direction == Direction.outbound,
            subject=payload.subject,
            full_visible_text=text_result.get("full_visible_text"),
            html_present=bool(payload.body_html and payload.body_html.strip()),
            text_present=bool(payload.body_plain and payload.body_plain.strip()),
            sender=participants.sender,
            to=participants.to_list,
            cc=participants.cc_list,
            bcc=participants.bcc_list,
            reply_to=participants.reply_to_list,
            participants=participants.all_participants,
            attachment_metadata=attachment_meta,
            normalization_version="v1",
            normalization_flags=flags,
            normalization_warnings=warnings,
        )

    def _extract_text(
        self,
        payload: RawEmailPayload,
        flags: list[NormalizationFlag],
    ) -> dict:
        """Extract and split text content. WO 4.7.1, 4.7.2, 4.7.3."""
        body_plain = payload.body_plain or ""
        body_html = payload.body_html or ""

        # Prefer plain text
        if body_plain.strip():
            result = QuotedTextParser.parse(body_plain)
        elif body_html.strip():
            result = QuotedTextParser.parse_html(body_html)
            flags.append(NormalizationFlag.html_only_body)
        else:
            flags.append(NormalizationFlag.missing_text_body)
            return {
                "latest_authored_text": "",
                "prior_context_text": None,
                "full_visible_text": None,
            }

        if result.quoted_text_detected:
            flags.append(NormalizationFlag.quoted_text_detected)
        if result.signature_detected:
            flags.append(NormalizationFlag.signature_detected)
        if result.missing_text_body:
            flags.append(NormalizationFlag.missing_text_body)

        return {
            "latest_authored_text": result.latest_authored_text,
            "prior_context_text": result.prior_context_text,
            "full_visible_text": result.full_visible_text,
        }

    def _extract_attachments(
        self,
        payload: RawEmailPayload,
        flags: list[NormalizationFlag],
    ) -> list[NormalizedAttachment]:
        """Extract attachment metadata. WO 4.7.6."""
        if not payload.attachment_metadata:
            return []

        flags.append(NormalizationFlag.attachment_present)

        attachments = []
        for att in payload.attachment_metadata:
            attachments.append(NormalizedAttachment(
                filename=att.get("filename"),
                mime_type=att.get("content_type") or att.get("mime_type"),
                size_bytes=att.get("size") or att.get("size_bytes"),
                provider_attachment_id=att.get("attachment_id") or att.get("provider_attachment_id"),
                is_inline=att.get("is_inline", False),
                has_content_fetched=att.get("has_content_fetched", False),
            ))

        return attachments


def _extract_thread_id(
    message_id: str,
    in_reply_to: str | None,
    references: str | None,
) -> str:
    """Extract root message ID as thread_id."""
    if references:
        refs = references.strip().split()
        if refs:
            return refs[0]
    if in_reply_to:
        return in_reply_to.strip()
    return message_id


def _detect_subtype(payload: RawEmailPayload) -> str | None:
    """Detect email subtype (reply, forward, etc.) from headers/subject."""
    subject = (payload.subject or "").strip().lower()

    if payload.in_reply_to or (payload.references and payload.references.strip()):
        if subject.startswith("fwd:") or subject.startswith("fw:"):
            return "forward"
        return "reply"

    if subject.startswith("fwd:") or subject.startswith("fw:"):
        return "forward"

    return None
