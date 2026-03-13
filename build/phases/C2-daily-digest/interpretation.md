# Phase C2 — Daily Digest: Interpretation

**Written by:** Claude Code
**Date:** 2026-03-13
**Stage:** STAGE 2 — INTERPRET

---

## What This Phase Does and Why

Phase C2 adds a daily digest feature that pushes a morning summary of surfaced commitments to the user via email — without them needing to open the app. This is the first outbound communication Rippled sends, and it's central to the product's retention mechanic: the system comes to you.

The digest pulls from the three existing surfacing surfaces (Main, Shortlist, Clarifications), formats them cleanly, and delivers via SMTP (with SendGrid as an optional upgrade). A `digest_log` table records every send attempt for audit and debugging. A Celery Beat task handles scheduling.

---

## Proposed Implementation

### Architecture

```
Celery Beat (08:00 daily)
       ↓
send_daily_digest() [Celery task]
       ↓
DigestAggregator.aggregate(session) → DigestData
       ├── Check user_settings.digest_enabled — skip if false
       ├── Check last_digest_sent_at — skip if already sent today
       ├── Query Main surface: top 5 by priority_score DESC
       ├── Query Shortlist: top 3 by priority_score DESC
       ├── Query Clarifications: any with observe_until expired
       └── Deduplicate across sections
       ↓
DigestFormatter.format(digest_data) → (subject, plain_text, html)
       ↓
DigestDelivery.send(subject, plain_text, html) → DeliveryResult
       ├── if SENDGRID_API_KEY → use SendGrid
       ├── elif SMTP configured → use smtplib
       └── else → log to stdout at INFO
       ↓
DigestLog row written (sent / skipped / failed)
UserSettings.last_digest_sent_at updated
```

### Key Files to Create/Modify

| File | Action |
|------|---------|
| `app/services/digest.py` | NEW — DigestAggregator, DigestFormatter, DigestDelivery |
| `app/tasks.py` | MODIFY — add `send_daily_digest` task + beat schedule entry |
| `app/models/orm.py` | MODIFY — add `DigestLog` and `UserSettings` ORM classes |
| `app/api/routes/digest.py` | NEW — 3 endpoints (trigger, log, preview) |
| `app/main.py` | MODIFY — register digest router |
| `app/core/config.py` | MODIFY — add 8 SMTP/SendGrid/digest settings |
| `migrations/versions/f0a1b2c3d4e5_phase_c2_daily_digest.py` | NEW — Alembic migration |
| `tests/services/test_digest.py` | NEW — 25+ unit tests |
| `tests/integration/test_digest_api.py` | NEW — integration tests for 3 endpoints |

---

### DigestService (`app/services/digest.py`)

Three focused classes, each with a single responsibility:

**DigestAggregator:**

```python
@dataclass
class DigestData:
    main: list[Commitment]
    shortlist: list[Commitment]
    clarifications: list[Commitment]
    generated_at: datetime
    is_empty: bool  # True if all three lists are empty

def aggregate(session: Session, user_id: str) -> DigestData
```

Query logic (all queries are synchronous — the Celery task uses `get_sync_session`):
- Main: `SELECT ... WHERE user_id = ? AND surfaced_as = 'main' AND lifecycle_state IN ('active', 'needs_clarification') ORDER BY priority_score DESC NULLS LAST LIMIT 5`
- Shortlist: same pattern, `surfaced_as = 'shortlist'`, `LIMIT 3`
- Clarifications: `surfaced_as = 'clarifications'` AND `observe_until <= now()` (ready for review), `LIMIT 5`

Deduplication: maintain a `seen_ids: set[str]` across all three sections. If a commitment ID appears in Main, skip it from Shortlist/Clarifications.

**DigestFormatter:**

```python
@dataclass
class FormattedDigest:
    subject: str
    plain_text: str
    html: str

def format(digest: DigestData, date: date | None = None) -> FormattedDigest
```

Subject line logic:
- Total commitment count > 0: `"Your Rippled digest — {date}"`
- (Empty digest never reaches the formatter — aggregator handles the skip signal)

Plain text format:
```
Your Rippled digest — March 13, 2026

🔴 BIG PROMISES (2)
1. Deploy the API redesign — deadline: Mar 15
2. Send Q1 report to client — no deadline set

📋 SHORTLIST (1)
1. Review PR from Sarah

⚠️  NEEDS CLARIFICATION (1)
1. "We'll handle that later" — owner unclear

---
Rippled.ai — commitment intelligence
```

HTML format: single `<style>` block with inline styles only. Three `<section>` blocks (one per surface). `<h2>` headers, `<ol>` numbered lists. Each item: `<li><strong>title</strong> — deadline or "no deadline"</li>`. No external resources, no images, no JavaScript. Renders in Gmail, Outlook, Apple Mail.

**DigestDelivery:**

```python
@dataclass
class DeliveryResult:
    method: str  # "smtp" | "sendgrid" | "stdout"
    success: bool
    error: str | None = None

def send(subject: str, plain_text: str, html: str) -> DeliveryResult
```

Delivery priority:
1. If `settings.sendgrid_api_key` is set → SendGrid via `sendgrid` library
2. Elif `settings.digest_smtp_host` is set → `smtplib.SMTP` with STARTTLS
3. Else → `logger.info("DIGEST: %s\n%s", subject, plain_text)` → returns `method="stdout"`

SMTP implementation uses stdlib only: `smtplib`, `email.mime.multipart.MIMEMultipart`, `email.mime.text.MIMEText`. No new dependencies unless SendGrid is used.

---

### Celery Task (`app/tasks.py`)

Following the exact pattern of existing tasks (module-level imports inside the function body to avoid circular imports at beat schedule load time):

```python
@celery_app.task(name="app.tasks.send_daily_digest")
def send_daily_digest() -> dict:
    """Build and send the daily digest — Phase C2."""
    from app.services.digest import DigestAggregator, DigestFormatter, DigestDelivery
    from app.models.orm import UserSettings, DigestLog
    from datetime import datetime, timezone, date
    ...
```

Beat schedule entry (added to `celery_app.conf.update` dict):
```python
"daily-digest": {
    "task": "app.tasks.send_daily_digest",
    "schedule": crontab(hour=8, minute=0),
},
```

Idempotency check: before calling the aggregator, load `UserSettings` for the configured `digest_to_email`. If `last_digest_sent_at` is today (UTC date comparison), return `{"status": "skipped", "reason": "already_sent_today"}`.

The task writes a `DigestLog` row regardless of outcome (sent / skipped / failed). On failure, the exception is caught, logged, and the `DigestLog` row records `status="failed"` + `error_message`.

**Open question Q1 — user identity in Celery task:** The digest is a system-level task, not per-user-request. For MVP, it pulls the user by `digest_to_email` config. The WO says "configured user" which aligns with the single-user MVP assumption. This means the task doesn't need a user_id parameter. Recommended: derive user from `settings.digest_to_email` by querying `SELECT id FROM users WHERE email = ?`. If no user found, log and skip.

---

### ORM Changes (`app/models/orm.py`)

**`user_settings` table does not exist** — confirmed by codebase search. It must be created.

```python
class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(_uuid(), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    digest_enabled: Mapped[bool] = mapped_column(Boolean, server_default="true", nullable=False)
    digest_time: Mapped[str] = mapped_column(String(5), server_default="08:00", nullable=False)
    last_digest_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

`user_id` as primary key (one settings row per user). No separate `id` UUID needed.

```python
class DigestLog(Base):
    __tablename__ = "digest_log"

    id: Mapped[str] = mapped_column(_uuid(), primary_key=True, server_default=func.gen_random_uuid())
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    commitment_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    delivery_method: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    digest_content: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

Note: `DigestLog` is not foreign-keyed to `users` — it's a system audit table. The digest is system-level for MVP.

---

### Migration (`migrations/versions/f0a1b2c3d4e5_phase_c2_daily_digest.py`)

- `down_revision = "e9f0a1b2c3d4"` (Phase C1 model detection)
- Creates `user_settings` table
- Creates `digest_log` table
- No enum types needed (all new columns use built-in types)

---

### Config (`app/core/config.py`)

Add to `Settings`:
```python
# Digest / email delivery
digest_enabled: bool = True
digest_smtp_host: str = ""
digest_smtp_port: int = 587
digest_smtp_user: str = ""
digest_smtp_pass: str = ""
digest_from_email: str = "digest@rippled.ai"
digest_to_email: str = ""
sendgrid_api_key: str = ""
```

`digest_to_email` is blank by default — if not set, the delivery layer falls through to stdout mode (useful for dev).

---

### API Routes (`app/api/routes/digest.py`)

Following the `surface.py` pattern: `APIRouter`, async endpoints, `get_current_user_id` dependency, `get_db` session.

```python
router = APIRouter(prefix="/digest", tags=["digest"])

POST /digest/trigger   → DigestTriggerResponse
GET  /digest/log       → list[DigestLogRead]
GET  /digest/preview   → DigestPreviewResponse
```

`POST /digest/trigger`: Calls `DigestAggregator.aggregate()`, then `DigestFormatter.format()`, then `DigestDelivery.send()`. Writes `DigestLog`. Returns status dict.

`GET /digest/log`: Returns last 10 `DigestLog` rows ordered by `sent_at DESC`.

`GET /digest/preview`: Calls aggregator + formatter but does NOT send. Returns `{main: [...], shortlist: [...], clarifications: [...], subject: str, generated_at: datetime}`.

**Open question Q2 — async vs sync in API routes:** The API routes use `AsyncSession` (standard pattern). But `DigestAggregator` is designed for the Celery task which uses `get_sync_session`. Recommended solution: `DigestAggregator` accepts a `Session` (sync) OR `AsyncSession` (async) — implemented as two separate methods: `aggregate_sync(session)` for Celery, `aggregate_async(session)` for the API. This keeps the service usable in both contexts without introducing threading complexity.

Registration in `app/main.py`:
```python
from app.api.routes import digest as digest_routes
app.include_router(digest_routes.router, prefix=settings.api_prefix, tags=["digest"])
```

---

### SendGrid Dependency

If `settings.sendgrid_api_key` is set, `DigestDelivery` uses the `sendgrid` library. This is an **optional** dependency — the SMTP fallback covers all cases without it. Add to `requirements.txt` conditionally.

**Recommended answer (Q3 — SendGrid):** Include `sendgrid` in `requirements.txt` unconditionally. It's small, and the conditional import pattern (`try: import sendgrid` at call site) is less clean than a declared dependency. The library is only instantiated when the API key is present.

---

## Open Questions with Recommended Answers

### Q1: User identity in digest task
**Issue:** The Celery task runs without a request context. How does it identify the user to generate a digest for?
**Recommendation:** For MVP (single-user), derive the user from `settings.digest_to_email`. Query `users` table by email. If no match, log WARNING and skip. This avoids adding a `user_id` config field and stays consistent with the single-user assumption already present in the IMAP/Slack connectors.

### Q2: Async vs sync in DigestAggregator
**Issue:** The service must work in both Celery (sync session) and FastAPI (async session) contexts.
**Recommendation:** Implement both `aggregate_sync(session: Session)` and `aggregate_async(session: AsyncSession)` on `DigestAggregator`. The query logic is identical — just `session.execute()` vs `await session.execute()`. This is cleaner than a single method that tries to detect session type at runtime.

### Q3: SendGrid as optional dependency
**Issue:** WO says "if SENDGRID_API_KEY is set, use SendGrid instead of SMTP."
**Recommendation:** Add `sendgrid` to `requirements.txt` unconditionally. Import at call site inside `DigestDelivery.send()`. This avoids messy conditional imports and documents the dependency clearly.

### Q4: `observe_until` filter for Clarifications section
**Issue:** The WO says "Pull from Clarifications: any with observe_until expired." But `Commitment.observe_until` tracks the observation window for the commitment itself — is this the right filter for the Clarifications surface?
**Recommendation:** Filter on `surfaced_as = 'clarifications'` AND `lifecycle_state IN ('active', 'needs_clarification')`. The `observe_until` filter for the Clarifications surface is ambiguous (a commitment can be on the clarifications surface without its observation window being expired — it may have been promoted directly). The simpler and correct filter is surface + state. However, I will add `observe_until IS NULL OR observe_until <= now()` as a secondary condition to match the WO intent.

### Q5: `digest_content` JSONB snapshot format
**Issue:** What structure should `digest_content` store?
**Recommendation:** Store a minimal dict:
```json
{
  "main": [{"id": "...", "title": "...", "deadline": "..."}],
  "shortlist": [...],
  "clarifications": [...],
  "subject": "Your Rippled digest — March 13, 2026"
}
```
This is an audit snapshot — enough to reconstruct what the user received, without duplicating the full ORM structure.

---

## Test Plan

**Unit tests (`tests/services/test_digest.py`):**
- `DigestAggregator`: mock DB session, verify correct surface queries, correct limit (5/3/5), deduplication logic, empty digest flag
- `DigestFormatter`: plain text output format, HTML output contains key structural elements, subject line format, deadline display
- `DigestDelivery`: SMTP mock (verify `smtplib.SMTP` called with correct args), SendGrid mock, stdout fallback
- Celery task: idempotency (already sent today → skip), `digest_enabled=False` → skip, user not found → skip

**Integration tests (`tests/integration/test_digest_api.py`):**
- `POST /digest/trigger` → 200 with status dict
- `GET /digest/log` → 200 with list (empty initially)
- `GET /digest/preview` → 200 with digest structure (no send side-effects)

Minimum 25 tests target is achievable: ~15 unit + 10 integration.

---

## Risk Assessment

- **Regression risk: LOW** — no changes to existing detection/surfacing/clarification pipelines. Only additions.
- **Migration risk: LOW** — two new tables, no changes to existing tables, no new enum types.
- **Email delivery risk: LOW** — stdout fallback means the feature works in all environments without SMTP config. No blast radius.
- **Idempotency:** Beat task checks `last_digest_sent_at` before sending. Calling `POST /digest/trigger` twice in a day via API will NOT check idempotency (it's a manual override for testing). The Celery task check and the API trigger are intentionally separate.
- **No breaking changes to existing APIs or ORM structure.**
