"""Daily digest service — Phase C2.

Three components:
- DigestAggregator: queries surfaced commitments from the DB
- DigestFormatter: renders the digest as plain-text and HTML
- DigestDelivery: sends via SMTP, SendGrid, or logs to stdout
"""
from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.orm import Commitment

if TYPE_CHECKING:
    from app.core.config import Settings

logger = logging.getLogger(__name__)

_SURFACED_STATES = ("active", "needs_clarification")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DigestData:
    main: list
    shortlist: list
    clarifications: list
    generated_at: datetime
    is_empty: bool


@dataclass
class FormattedDigest:
    subject: str
    plain_text: str
    html: str


@dataclass
class DeliveryResult:
    method: str  # "smtp" | "sendgrid" | "stdout"
    success: bool
    error: str | None = None


# ---------------------------------------------------------------------------
# DigestAggregator
# ---------------------------------------------------------------------------

class DigestAggregator:
    """Pulls commitments from the three surfacing surfaces and deduplicates."""

    def aggregate_sync(self, session: Session, user_id: str) -> DigestData:
        """Aggregate digest for a user using a synchronous DB session (Celery)."""
        main_rows = session.execute(
            select(Commitment)
            .where(
                and_(
                    Commitment.user_id == user_id,
                    Commitment.surfaced_as == "main",
                    Commitment.lifecycle_state.in_(_SURFACED_STATES),
                )
            )
            .order_by(Commitment.priority_score.desc().nullslast())
            .limit(5)
        ).scalars().all()

        seen_ids: set[str] = {c.id for c in main_rows}

        shortlist_rows = [
            c for c in session.execute(
                select(Commitment)
                .where(
                    and_(
                        Commitment.user_id == user_id,
                        Commitment.surfaced_as == "shortlist",
                        Commitment.lifecycle_state.in_(_SURFACED_STATES),
                    )
                )
                .order_by(Commitment.priority_score.desc().nullslast())
                .limit(3)
            ).scalars().all()
            if c.id not in seen_ids
        ]
        seen_ids.update(c.id for c in shortlist_rows)

        clarification_rows = [
            c for c in session.execute(
                select(Commitment)
                .where(
                    and_(
                        Commitment.user_id == user_id,
                        Commitment.surfaced_as == "clarifications",
                        Commitment.lifecycle_state.in_(_SURFACED_STATES),
                    )
                )
                .order_by(Commitment.priority_score.desc().nullslast())
                .limit(5)
            ).scalars().all()
            if c.id not in seen_ids
        ]

        is_empty = not main_rows and not shortlist_rows and not clarification_rows

        return DigestData(
            main=list(main_rows),
            shortlist=shortlist_rows,
            clarifications=clarification_rows,
            generated_at=datetime.now(timezone.utc),
            is_empty=is_empty,
        )

    async def aggregate_async(self, session: AsyncSession, user_id: str) -> DigestData:
        """Aggregate digest for a user using an async DB session (FastAPI routes)."""
        main_result = await session.execute(
            select(Commitment)
            .where(
                and_(
                    Commitment.user_id == user_id,
                    Commitment.surfaced_as == "main",
                    Commitment.lifecycle_state.in_(_SURFACED_STATES),
                )
            )
            .order_by(Commitment.priority_score.desc().nullslast())
            .limit(5)
        )
        main_rows = main_result.scalars().all()
        seen_ids: set[str] = {c.id for c in main_rows}

        shortlist_result = await session.execute(
            select(Commitment)
            .where(
                and_(
                    Commitment.user_id == user_id,
                    Commitment.surfaced_as == "shortlist",
                    Commitment.lifecycle_state.in_(_SURFACED_STATES),
                )
            )
            .order_by(Commitment.priority_score.desc().nullslast())
            .limit(3)
        )
        shortlist_rows = [c for c in shortlist_result.scalars().all() if c.id not in seen_ids]
        seen_ids.update(c.id for c in shortlist_rows)

        clarification_result = await session.execute(
            select(Commitment)
            .where(
                and_(
                    Commitment.user_id == user_id,
                    Commitment.surfaced_as == "clarifications",
                    Commitment.lifecycle_state.in_(_SURFACED_STATES),
                )
            )
            .order_by(Commitment.priority_score.desc().nullslast())
            .limit(5)
        )
        clarification_rows = [
            c for c in clarification_result.scalars().all() if c.id not in seen_ids
        ]

        is_empty = not main_rows and not shortlist_rows and not clarification_rows

        return DigestData(
            main=list(main_rows),
            shortlist=shortlist_rows,
            clarifications=clarification_rows,
            generated_at=datetime.now(timezone.utc),
            is_empty=is_empty,
        )


# ---------------------------------------------------------------------------
# DigestFormatter
# ---------------------------------------------------------------------------

_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _fmt_deadline(dt: datetime | None) -> str:
    if dt is None:
        return "no deadline set"
    return dt.strftime("%b %d, %Y").replace(" 0", " ")


class DigestFormatter:
    """Renders a DigestData into subject, plain-text, and HTML email bodies."""

    def format(self, digest: DigestData, for_date: date | None = None) -> FormattedDigest:
        if for_date is None:
            for_date = digest.generated_at.date()

        month_name = _MONTH_NAMES[for_date.month]
        date_str = f"{month_name} {for_date.day}, {for_date.year}"
        subject = f"Your Rippled digest — {date_str}"

        plain_text = self._build_plain_text(digest, date_str)
        html = self._build_html(digest, date_str)

        return FormattedDigest(subject=subject, plain_text=plain_text, html=html)

    def _build_plain_text(self, digest: DigestData, date_str: str) -> str:
        lines = [f"Your Rippled digest — {date_str}", ""]

        if digest.main:
            lines.append(f"🔴 BIG PROMISES ({len(digest.main)})")
            for i, c in enumerate(digest.main, 1):
                deadline = _fmt_deadline(getattr(c, "resolved_deadline", None))
                lines.append(f"{i}. {c.title} — {deadline}")
            lines.append("")

        if digest.shortlist:
            lines.append(f"📋 SHORTLIST ({len(digest.shortlist)})")
            for i, c in enumerate(digest.shortlist, 1):
                deadline = _fmt_deadline(getattr(c, "resolved_deadline", None))
                lines.append(f"{i}. {c.title} — {deadline}")
            lines.append("")

        if digest.clarifications:
            lines.append(f"⚠️  NEEDS CLARIFICATION ({len(digest.clarifications)})")
            for i, c in enumerate(digest.clarifications, 1):
                deadline = _fmt_deadline(getattr(c, "resolved_deadline", None))
                lines.append(f"{i}. {c.title} — {deadline}")
            lines.append("")

        lines.append("---")
        lines.append("Rippled.ai — commitment intelligence")
        return "\n".join(lines)

    def _build_html(self, digest: DigestData, date_str: str) -> str:
        sections = []

        if digest.main:
            items_html = "\n".join(
                f'<li><strong>{c.title}</strong> &mdash; {_fmt_deadline(getattr(c, "resolved_deadline", None))}</li>'
                for c in digest.main
            )
            sections.append(
                f'<section style="margin-bottom:24px">'
                f'<h2 style="color:#c0392b;font-size:14px;text-transform:uppercase;margin:0 0 8px">Big Promises</h2>'
                f'<ol style="margin:0;padding-left:20px;font-size:14px;line-height:1.6">{items_html}</ol>'
                f'</section>'
            )

        if digest.shortlist:
            items_html = "\n".join(
                f'<li><strong>{c.title}</strong> &mdash; {_fmt_deadline(getattr(c, "resolved_deadline", None))}</li>'
                for c in digest.shortlist
            )
            sections.append(
                f'<section style="margin-bottom:24px">'
                f'<h2 style="color:#2980b9;font-size:14px;text-transform:uppercase;margin:0 0 8px">Shortlist</h2>'
                f'<ol style="margin:0;padding-left:20px;font-size:14px;line-height:1.6">{items_html}</ol>'
                f'</section>'
            )

        if digest.clarifications:
            items_html = "\n".join(
                f'<li><strong>{c.title}</strong> &mdash; {_fmt_deadline(getattr(c, "resolved_deadline", None))}</li>'
                for c in digest.clarifications
            )
            sections.append(
                f'<section style="margin-bottom:24px">'
                f'<h2 style="color:#e67e22;font-size:14px;text-transform:uppercase;margin:0 0 8px">Needs Clarification</h2>'
                f'<ol style="margin:0;padding-left:20px;font-size:14px;line-height:1.6">{items_html}</ol>'
                f'</section>'
            )

        body_content = "\n".join(sections) if sections else "<p>No commitments to review today.</p>"

        return (
            '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
            '<body style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:24px;color:#333">'
            f'<h1 style="font-size:18px;margin:0 0 24px">Your Rippled digest — {date_str}</h1>'
            f'{body_content}'
            '<hr style="border:none;border-top:1px solid #eee;margin:24px 0">'
            '<p style="font-size:12px;color:#999">Rippled.ai — commitment intelligence</p>'
            '</body></html>'
        )


# ---------------------------------------------------------------------------
# DigestDelivery
# ---------------------------------------------------------------------------

class DigestDelivery:
    """Sends a formatted digest via SMTP, SendGrid, or stdout fallback."""

    def __init__(self, settings: "Settings | None" = None) -> None:
        if settings is None:
            from app.core.config import get_settings
            settings = get_settings()
        self._settings = settings

    def send(self, subject: str, plain_text: str, html: str) -> DeliveryResult:
        s = self._settings
        if s.sendgrid_api_key:
            return self._send_sendgrid(subject, plain_text, html)
        if s.digest_smtp_host:
            return self._send_smtp(subject, plain_text, html)
        return self._send_stdout(subject, plain_text)

    def _send_smtp(self, subject: str, plain_text: str, html: str) -> DeliveryResult:
        s = self._settings
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = s.digest_from_email
        msg["To"] = s.digest_to_email
        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html, "html"))
        try:
            with smtplib.SMTP(s.digest_smtp_host, s.digest_smtp_port) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(s.digest_smtp_user, s.digest_smtp_pass)
                smtp.sendmail(s.digest_from_email, s.digest_to_email, msg.as_string())
            logger.info("Digest sent via SMTP to %s", s.digest_to_email)
            return DeliveryResult(method="smtp", success=True)
        except smtplib.SMTPException as exc:
            logger.error("Digest SMTP send failed: %s", exc)
            return DeliveryResult(method="smtp", success=False, error=str(exc))
        except Exception as exc:
            logger.error("Digest SMTP unexpected error: %s", exc)
            return DeliveryResult(method="smtp", success=False, error=str(exc))

    def _send_sendgrid(self, subject: str, plain_text: str, html: str) -> DeliveryResult:
        s = self._settings
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail

            message = Mail(
                from_email=s.digest_from_email,
                to_emails=s.digest_to_email,
                subject=subject,
                plain_text_content=plain_text,
                html_content=html,
            )
            client = sendgrid.SendGridAPIClient(s.sendgrid_api_key)
            response = client.send(message)
            logger.info("Digest sent via SendGrid, status=%s", response.status_code)
            return DeliveryResult(method="sendgrid", success=True)
        except Exception as exc:
            logger.error("Digest SendGrid send failed: %s", exc)
            return DeliveryResult(method="sendgrid", success=False, error=str(exc))

    def _send_stdout(self, subject: str, plain_text: str) -> DeliveryResult:
        logger.info("DIGEST (stdout): %s\n%s", subject, plain_text)
        return DeliveryResult(method="stdout", success=True)
