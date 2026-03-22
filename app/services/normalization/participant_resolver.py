"""ParticipantResolver — normalize participant structures and identify primary user.

Implements WO sections 4.7.4 (direction detection), 4.7.5 (participant normalization).
"""

from dataclasses import dataclass, field

from app.connectors.shared.normalized_signal import NormalizedParticipant
from app.models.enums import Direction, ParticipantRole


@dataclass
class ResolvedParticipants:
    """All resolved participants from an email."""

    sender: NormalizedParticipant | None = None
    to_list: list[NormalizedParticipant] = field(default_factory=list)
    cc_list: list[NormalizedParticipant] = field(default_factory=list)
    bcc_list: list[NormalizedParticipant] = field(default_factory=list)
    reply_to_list: list[NormalizedParticipant] = field(default_factory=list)
    all_participants: list[NormalizedParticipant] = field(default_factory=list)


class ParticipantResolver:
    """Normalize participant structures and detect direction."""

    @staticmethod
    def detect_direction(
        sender_email: str | None,
        user_email: str,
        recipient_emails: list[str],
    ) -> Direction:
        """Detect email direction from account identity.

        sender == user → outbound
        recipient == user && sender != user → inbound
        else → unknown
        """
        if not sender_email:
            return Direction.unknown

        sender_norm = sender_email.strip().lower()
        user_norm = user_email.strip().lower()

        if sender_norm == user_norm:
            return Direction.outbound

        recipient_norms = [e.strip().lower() for e in recipient_emails]
        if user_norm in recipient_norms and sender_norm != user_norm:
            return Direction.inbound

        return Direction.unknown

    @staticmethod
    def normalize_participant(
        email: str | None,
        display_name: str | None,
        role: ParticipantRole,
        user_email: str,
    ) -> NormalizedParticipant:
        """Normalize a single participant.

        - Lowercase and trim email
        - Trim display name
        - Set is_primary_user flag
        - Do not invent missing emails
        """
        norm_email = email.strip().lower() if email else None
        norm_name = display_name.strip() if display_name else None
        user_norm = user_email.strip().lower()

        is_primary = norm_email is not None and norm_email == user_norm

        return NormalizedParticipant(
            email=norm_email,
            display_name=norm_name,
            role=role,
            is_primary_user=is_primary,
        )

    @staticmethod
    def normalize_all(
        sender_email: str | None,
        sender_name: str | None,
        to_emails: list[str],
        cc_emails: list[str],
        bcc_emails: list[str],
        reply_to_emails: list[str],
        user_email: str,
    ) -> ResolvedParticipants:
        """Normalize all participants from an email."""
        resolver = ParticipantResolver

        sender = None
        if sender_email:
            sender = resolver.normalize_participant(
                email=sender_email,
                display_name=sender_name,
                role=ParticipantRole.sender,
                user_email=user_email,
            )

        to_list = [
            resolver.normalize_participant(
                email=e, display_name=None, role=ParticipantRole.to, user_email=user_email,
            )
            for e in to_emails
        ]

        cc_list = [
            resolver.normalize_participant(
                email=e, display_name=None, role=ParticipantRole.cc, user_email=user_email,
            )
            for e in cc_emails
        ]

        bcc_list = [
            resolver.normalize_participant(
                email=e, display_name=None, role=ParticipantRole.bcc, user_email=user_email,
            )
            for e in bcc_emails
        ]

        reply_to_list = [
            resolver.normalize_participant(
                email=e, display_name=None, role=ParticipantRole.reply_to, user_email=user_email,
            )
            for e in reply_to_emails
        ]

        # All participants = sender + to + cc + bcc + reply_to (deduplicated by email)
        all_participants: list[NormalizedParticipant] = []
        seen_emails: set[str] = set()

        for p in ([sender] if sender else []) + to_list + cc_list + bcc_list + reply_to_list:
            key = p.email or id(p)  # use object id for participants without email
            if isinstance(key, str) and key in seen_emails:
                continue
            if isinstance(key, str):
                seen_emails.add(key)
            all_participants.append(p)

        return ResolvedParticipants(
            sender=sender,
            to_list=to_list,
            cc_list=cc_list,
            bcc_list=bcc_list,
            reply_to_list=reply_to_list,
            all_participants=all_participants,
        )
