"""IMAP polling logic for email connector.

Fetches unseen messages from INBOX and Sent folder, normalises them,
and ingests into the pipeline.
"""
import email as email_lib
import imaplib
import logging
import socket
import time
from datetime import datetime, timedelta, timezone
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime

from sqlalchemy import select

from app.connectors.email.normalizer import normalise_email
from app.connectors.email.schemas import RawEmailPayload
from app.connectors.shared.credentials_utils import decrypt_credentials
from app.connectors.shared.ingestor import get_or_create_source_sync, ingest_item
from app.core.config import get_settings
from app.db.session import get_sync_session
from app.models.orm import Source

logger = logging.getLogger(__name__)

BACKFILL_DAYS = 30

# Retry config for transient DNS / connection errors
_MAX_CONNECT_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 2  # doubles each retry: 2s, 4s

# Errors worth retrying (DNS resolution, transient network)
_RETRYABLE_ERRORS = (socket.gaierror, ConnectionRefusedError, ConnectionResetError, OSError)


def _build_search_criteria(last_synced_at: datetime | None) -> str:
    """Build IMAP search criteria based on sync state.

    - First sync (last_synced_at is None): SINCE <30 days ago>
    - Subsequent syncs: SINCE <last_synced_at date>
    """
    if last_synced_at is None:
        since_date = datetime.now(timezone.utc) - timedelta(days=BACKFILL_DAYS)
    else:
        since_date = last_synced_at
    # IMAP SINCE uses dd-Mon-yyyy format
    date_str = since_date.strftime("%d-%b-%Y")
    return f'SINCE {date_str}'


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


def _poll_source(source: Source) -> dict:
    """Poll a single email Source. Returns {ingested, duplicates, errors}.

    Reads credentials from source.credentials (with env-var fallback for
    backward compatibility), then connects via IMAP and ingests messages.

    First sync (last_synced_at is null): fetches emails from the last 30 days.
    Subsequent syncs: fetches emails since last_synced_at (incremental).
    Updates source.last_synced_at after a successful sync.
    """
    settings = get_settings()

    creds: dict = {}
    if source.credentials:
        creds = decrypt_credentials(source.credentials)

    # Sanitize hostname and user — strip whitespace to prevent DNS failures
    host = (creds.get("imap_host") or settings.imap_host or "").strip()
    port = int(creds.get("imap_port") or settings.imap_port or 993)
    ssl = creds.get("imap_ssl", None)
    if ssl is None:
        ssl = settings.imap_ssl if settings.imap_ssl is not None else True
    user = (creds.get("imap_user") or settings.imap_user or "").strip()
    password = creds.get("imap_password") or settings.imap_password
    sent_folder = creds.get("imap_sent_folder") or settings.imap_sent_folder or "Sent"

    if not host or not user:
        logger.info("Email source %s has no IMAP host/user — skipping", source.id)
        return {"ingested": 0, "duplicates": 0, "errors": 0, "skipped": True}

    ingested = 0
    duplicates = 0
    errors = 0
    user_id = source.user_id
    source_id = source.id

    conn = None
    try:
        # Retry IMAP connection on transient DNS/network errors
        logger.info(
            "Connecting to IMAP host=%s port=%d ssl=%s for source %s",
            host, port, ssl, source_id,
        )
        for attempt in range(1, _MAX_CONNECT_ATTEMPTS + 1):
            try:
                if ssl:
                    conn = imaplib.IMAP4_SSL(host, port)
                else:
                    conn = imaplib.IMAP4(host, port)
                break  # connected successfully
            except _RETRYABLE_ERRORS as exc:
                if attempt < _MAX_CONNECT_ATTEMPTS:
                    wait = _RETRY_BACKOFF_SECONDS * (2 ** (attempt - 1))
                    logger.warning(
                        "IMAP connection attempt %d/%d failed for host=%s source=%s: %s — retrying in %ds",
                        attempt, _MAX_CONNECT_ATTEMPTS, host, source_id, exc, wait,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "IMAP connection failed after %d attempts for host=%s source=%s: %s",
                        _MAX_CONNECT_ATTEMPTS, host, source_id, exc,
                    )
                    raise

        conn.login(user, password)

        search_criteria = _build_search_criteria(source.last_synced_at)
        is_backfill = source.last_synced_at is None
        if is_backfill:
            logger.info(
                "First sync for source %s — backfilling last %d days",
                source_id, BACKFILL_DAYS,
            )

        folders = [("INBOX", "inbound"), (sent_folder, "outbound")]

        for folder, direction in folders:
            try:
                status, _ = conn.select(folder, readonly=True)
                if status != "OK":
                    logger.warning("IMAP folder %s not found for source %s — skipping", folder, source_id)
                    continue

                _, data = conn.search(None, search_criteria)
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
                        logger.error("Error processing IMAP message %s for source %s: %s", num, source_id, e)
                        errors += 1

            except Exception as e:
                logger.error("Error accessing IMAP folder %s for source %s: %s", folder, source_id, e)

    finally:
        if conn:
            try:
                conn.logout()
            except Exception:
                pass

    # Update last_synced_at after successful sync
    with get_sync_session() as db:
        db_source = db.get(Source, source_id)
        if db_source:
            db_source.last_synced_at = datetime.now(timezone.utc)

    return {"ingested": ingested, "duplicates": duplicates, "errors": errors}


def poll_all_email_sources() -> dict:
    """Poll all active email Sources, using per-source credentials.

    Returns summary: {total_ingested, total_duplicates, total_errors, sources_polled, sources_failed}
    """
    with get_sync_session() as db:
        sources = db.execute(
            select(Source).where(
                Source.source_type == "email",
                Source.is_active.is_(True),
            )
        ).scalars().all()

    total: dict = {
        "ingested": 0,
        "duplicates": 0,
        "errors": 0,
        "sources_polled": 0,
        "sources_failed": 0,
    }

    for source in sources:
        try:
            result = _poll_source(source)
            total["ingested"] += result.get("ingested", 0)
            total["duplicates"] += result.get("duplicates", 0)
            total["errors"] += result.get("errors", 0)
            total["sources_polled"] += 1
        except Exception as e:
            logger.error("Email source %s failed: %s", source.id, e)
            total["sources_failed"] += 1

    return total


def poll_new_messages(user_id: str) -> dict:
    """Connect to IMAP, fetch unseen messages, normalise, and ingest.

    DEPRECATED: backward-compat wrapper using global env-var config.
    Use poll_all_email_sources() for multi-user operation.

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
