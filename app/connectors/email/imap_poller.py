"""IMAP polling logic for email connector.

Fetches unseen messages from INBOX and Sent folder, normalises them,
and ingests into the pipeline.
"""
import email as email_lib
import imaplib
import logging
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime

from app.connectors.email.normalizer import normalise_email
from app.connectors.email.schemas import RawEmailPayload
from app.connectors.shared.ingestor import get_or_create_source_sync, ingest_item
from app.core.config import get_settings
from app.db.session import get_sync_session

logger = logging.getLogger(__name__)


def _decode_header_value(value: str | None) -> str:
    """Decode email header value (handles encoded-word syntax)."""
    if not value:
        return ""
    parts = decode_header(value)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return " ".join(decoded)


def _get_body(msg: email_lib.message.Message) -> tuple[str, str]:
    """Extract plain text and HTML body from email message."""
    plain = ""
    html = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain" and not plain:
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                plain = payload.decode(charset, errors="replace") if payload else ""
            elif ctype == "text/html" and not html:
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                html = payload.decode(charset, errors="replace") if payload else ""
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or "utf-8"
        content = payload.decode(charset, errors="replace") if payload else ""
        if msg.get_content_type() == "text/html":
            html = content
        else:
            plain = content
    return plain, html


def _parse_email_message(
    raw: bytes,
    direction: str,
) -> RawEmailPayload | None:
    """Parse a raw email bytes into RawEmailPayload."""
    try:
        msg = email_lib.message_from_bytes(raw)
    except Exception:
        return None

    message_id = (msg.get("Message-ID") or "").strip()
    if not message_id:
        return None

    in_reply_to = (msg.get("In-Reply-To") or "").strip() or None
    references = (msg.get("References") or "").strip() or None

    from_raw = msg.get("From") or ""
    from_name, from_email = parseaddr(_decode_header_value(from_raw))

    to_raw = msg.get("To") or ""
    to_list = [addr for _, addr in [parseaddr(a.strip()) for a in to_raw.split(",")] if addr]

    cc_raw = msg.get("Cc") or ""
    cc_list = [addr for _, addr in [parseaddr(a.strip()) for a in cc_raw.split(",")] if addr] if cc_raw else []

    subject = _decode_header_value(msg.get("Subject") or "")

    date_str = msg.get("Date")
    try:
        date = parsedate_to_datetime(date_str) if date_str else datetime.now(timezone.utc)
    except Exception:
        date = datetime.now(timezone.utc)

    plain, html = _get_body(msg)

    # Detect attachments
    has_attachment = False
    attachment_metadata = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                has_attachment = True
                attachment_metadata.append({
                    "filename": _decode_header_value(part.get_filename() or ""),
                    "content_type": part.get_content_type(),
                })

    return RawEmailPayload(
        message_id=message_id,
        in_reply_to=in_reply_to,
        references=references,
        from_name=from_name or None,
        from_email=from_email,
        to=to_list,
        cc=cc_list,
        subject=subject,
        body_plain=plain,
        body_html=html,
        date=date,
        direction=direction,
        has_attachment=has_attachment,
        attachment_metadata=attachment_metadata if attachment_metadata else None,
    )


def poll_new_messages(user_id: str) -> dict:
    """Connect to IMAP, fetch unseen messages, normalise, and ingest.

    Returns a summary dict with counts of processed messages.
    """
    settings = get_settings()

    if not settings.imap_host or not settings.imap_user:
        logger.info("IMAP not configured — skipping poll")
        return {"skipped": True, "reason": "imap_not_configured"}

    ingested = 0
    duplicates = 0
    errors = 0

    try:
        if settings.imap_ssl:
            conn = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port)
        else:
            conn = imaplib.IMAP4(settings.imap_host, settings.imap_port)

        conn.login(settings.imap_user, settings.imap_password)

        folders = [("INBOX", "inbound"), (settings.imap_sent_folder, "outbound")]

        with get_sync_session() as db:
            source = get_or_create_source_sync(
                user_id=user_id,
                source_type="email",
                provider_account_id=settings.imap_user,
                db=db,
            )
            source_id = source.id

        for folder, direction in folders:
            try:
                status, _ = conn.select(folder, readonly=True)
                if status != "OK":
                    logger.warning("IMAP folder %s not found — skipping", folder)
                    continue

                _, data = conn.search(None, "UNSEEN")
                message_nums = data[0].split() if data[0] else []

                for num in message_nums:
                    try:
                        _, msg_data = conn.fetch(num, "(RFC822)")
                        if not msg_data or not msg_data[0]:
                            continue
                        raw = msg_data[0][1]
                        if not isinstance(raw, bytes):
                            continue

                        payload = _parse_email_message(raw, direction)
                        if not payload:
                            continue

                        with get_sync_session() as db:
                            item = normalise_email(payload, source_id)
                            _, created = ingest_item(item, user_id, db)
                            if created:
                                ingested += 1
                            else:
                                duplicates += 1

                    except Exception as e:
                        logger.error("Error processing IMAP message %s: %s", num, e)
                        errors += 1

            except Exception as e:
                logger.error("Error accessing IMAP folder %s: %s", folder, e)

        conn.logout()

    except Exception as e:
        logger.error("IMAP connection error: %s", e)
        return {"error": str(e), "ingested": ingested, "duplicates": duplicates, "errors": errors}

    return {"ingested": ingested, "duplicates": duplicates, "errors": errors}
