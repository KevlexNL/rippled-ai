# Phase 09 — Onboarding, Account Management & Multi-User: Interpretation

**Stage:** STAGE 2 — INTERPRET
**Date:** 2026-03-13

---

## 1. Summary Understanding

Phase 09 delivers three interconnected things that together make Rippled deployable to more than one person:

1. **Complete auth flows** — signup, login, forgot password, password reset, and log out. Currently only login exists (`LoginScreen.tsx`). There is no way for a new user to create an account, and no recovery path if a password is lost. This is a pre-deployment blocker.

2. **An onboarding wizard** — a guided, multi-step setup flow that walks a new user through connecting their signal inputs (email, Slack, meeting transcripts). This is not optional polish: without onboarding, a new user like Mitch has no mechanism to provide his IMAP credentials or Slack token. The system is inert until connectors are configured.

3. **Per-user credential isolation** — the architectural prerequisite for multi-user operation. Currently, IMAP and Slack credentials are global env vars in `app/core/config.py`. One set of credentials means one user. For Mitch to sign up and connect his own email and Slack independently, credentials must be stored per-user in `Source.credentials`. This is the most significant technical change Phase 09 introduces.

**Why this is required before deployment, not optional polish:**

The system currently cannot be used by anyone other than a developer who manually configures `.env`. There is no self-service path. Rippled cannot be tested with a second user (Mitch), and there is no recovery mechanism if Kevin's password is lost. Phase 09 is the minimum viable operational surface — the product cannot be properly used without it.

---

## 2. The Multi-User Credential Problem

### What currently lives in global env vars

From `app/core/config.py`, the following are single-user globals that must become per-user:

| Env var | What it does | Where it's consumed |
|---|---|---|
| `IMAP_HOST` | IMAP server hostname | `imap_poller.py:135` via `get_settings()` |
| `IMAP_PORT` | IMAP server port | `imap_poller.py:144` |
| `IMAP_USER` | Mailbox username / email address | `imap_poller.py:149`, also used as `provider_account_id` in `get_or_create_source_sync` |
| `IMAP_PASSWORD` | Mailbox password / app password | `imap_poller.py:149` |
| `IMAP_SSL` | Whether to use SSL | `imap_poller.py:143` |
| `IMAP_SENT_FOLDER` | Sent folder name (varies by provider) | `imap_poller.py:151` |
| `INTERNAL_DOMAINS` | Comma-separated list for internal/external classification | `participant_classifier.py` |
| `SLACK_BOT_TOKEN` | Bot token for Slack API | `tasks.py` Slack task |
| `SLACK_TEAM_ID` | Workspace ID — used to find the Slack Source | `tasks.py`, `normalizer.py` implicitly |
| `SLACK_USER_ID` | The Rippled user's Slack user ID | `tasks.py` |
| `SLACK_SIGNING_SECRET` | For verifying incoming Slack webhook signatures | `verifier.py` |

**What stays global (applies to the whole deployment, not per-user):**

- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY` — infrastructure
- `DATABASE_URL` — infrastructure
- `REDIS_URL` — infrastructure
- `OPENAI_API_KEY` — shared AI budget
- `SECRET_KEY` — app signing
- `EMAIL_WEBHOOK_SECRET` — validates inbound email webhook provider (not per-user — it is a deployment-level shared secret with SendGrid/Mailgun)
- `MEETING_WEBHOOK_SECRET` — same, deployment-level

**Summary:** Everything under "Email connector" and "Slack connector" in `config.py` (7 + 4 = 11 env vars) needs to become per-user. Everything else stays global.

### What to store in Source.credentials

`Source.credentials` is a `JSONB` column that currently exists but is never written to (`sources.py:create_source` does not accept `credentials`). It is the right place for per-user secrets.

Proposed schemas by source type:

**Email Source (`source_type = "email"`)**:
```json
{
  "imap_host": "imap.gmail.com",
  "imap_port": 993,
  "imap_user": "kevin@example.com",
  "imap_password": "app-password-here",
  "imap_ssl": true,
  "imap_sent_folder": "Sent",
  "internal_domains": "example.com,mycompany.com"
}
```

**Slack Source (`source_type = "slack"`)**:
```json
{
  "bot_token": "xoxb-...",
  "signing_secret": "abc123...",
  "team_id": "T0XXXXXX",
  "user_id": "U0XXXXXX"
}
```

**Meeting Source (`source_type = "meeting"`)**:
```json
{
  "webhook_secret": "optional-per-user-secret",
  "platform": "fireflies"
}
```

The `Source.provider_account_id` continues to be used as the human-readable account identifier (email address, Slack workspace name, Fireflies account ID).

### Security: how to store credentials at rest

**Three options:**

| Option | Security | Complexity | MVP-appropriate? |
|---|---|---|---|
| **Plaintext JSONB** | Weak — anyone with DB access can read all passwords | Zero | Acceptable for closed MVP with 2 known users |
| **Application-level encryption** | Good — secrets encrypted with a key only the app knows | Moderate — need key management, encrypt/decrypt on read/write | Yes — recommended |
| **Separate secrets table / Vault** | Strong — full key rotation, audit trail | High — overkill for MVP | No |

**Recommendation: application-level encryption, but with a pragmatic MVP approach.**

Use `cryptography` (Fernet symmetric encryption) with the existing `SECRET_KEY` env var as the key material. Before writing to `Source.credentials`, encrypt sensitive fields (passwords, tokens). On read, decrypt. This:
- Is simple to implement (under 40 lines)
- Requires no additional infrastructure
- Uses a secret that is already managed in Railway's env
- Is transparent to the rest of the codebase — callers get plaintext, encryption happens in a `credentials_utils.py` helper

The implementation: derive a Fernet key from `SECRET_KEY` using PBKDF2 (or directly if it is already 32 bytes). Store `{"_encrypted": true, ...}` so the code can detect whether a legacy plaintext record needs migration.

**What stays plaintext in `credentials`:** Non-secret config like `imap_host`, `imap_port`, `imap_ssl`, `imap_sent_folder`, `internal_domains`, `platform`. Only passwords and tokens are encrypted.

For a 2-person closed MVP (Kevin + Mitch), plaintext JSONB is technically "acceptable" for speed, but the encryption wrapper is 40 lines and prevents a bad habit from solidifying into production. **Recommendation: implement the encryption wrapper now.**

### How connectors change to use per-user credentials

**IMAP Poller (`app/connectors/email/imap_poller.py`):**

Current behaviour: `poll_new_messages(user_id: str)` reads credentials from global `get_settings()`.

New behaviour: `poll_new_messages()` (no `user_id` argument) iterates over **all active email Sources** in the database, loading per-source credentials. For each:

```python
def poll_new_messages() -> dict:
    with get_sync_session() as db:
        sources = db.execute(
            select(Source).where(
                Source.source_type == "email",
                Source.is_active == True,
                Source.credentials != None
            )
        ).scalars().all()

    for source in sources:
        creds = decrypt_credentials(source.credentials)
        _poll_source(source.id, source.user_id, creds)
```

The Celery beat task calls `poll_new_messages()` with no arguments. It polls for every connected user automatically.

**Slack task (`app/tasks.py` — `process_slack_event`):**

Current behaviour: looks up user by `SLACK_USER_ID` env var, gets signing secret from `SLACK_SIGNING_SECRET` env var.

New behaviour: The Slack webhook endpoint (`POST /webhooks/slack/events`) must remain stateless for the initial 3-second ack. However, the `team_id` in the Slack event payload identifies *which* workspace sent the event. The task resolves the Slack Source by `provider_account_id = team_id`, then loads `signing_secret` and `user_id` from that Source's credentials.

This means **Slack signature verification must move from per-deployment to per-Source**. The signing secret used for verification is fetched from `Source.credentials["signing_secret"]` for the workspace that matches the event's `team_id`. A consequence: a single deployment can handle Slack events from multiple workspaces (Kevin's workspace, Mitch's workspace) without any additional routing logic.

**Webhook endpoints (Slack, Email, Meeting):**

The existing `POST /webhooks/slack/events` endpoint uses `SLACK_SIGNING_SECRET` from global settings for HMAC verification. This needs to change: look up the Source by `team_id` from the event body, get the signing secret from its credentials, then verify. This requires a quick DB lookup before or during verification — acceptable because Slack gives 3 seconds and the lookup is a single indexed query.

The meeting transcript webhook currently uses Bearer auth (the user's Supabase JWT). This is fine — it remains per-user by design. No change needed.

### Backward compatibility during development

**Recommendation: maintain env var fallback with a deprecation log.**

If `Source.credentials` has no IMAP credentials, the IMAP poller falls back to global env vars (if set). This lets Kevin continue working during Phase 09 development without migrating his own credentials immediately. Once Phase 09 is deployed and Kevin completes onboarding, the env vars become redundant and can be removed in a follow-up cleanup.

```python
creds = source.credentials or {}
imap_host = creds.get("imap_host") or settings.imap_host
# log warning if falling back to env var
```

This fallback disappears once Kevin completes onboarding.

---

## 3. Auth Flows

Supabase handles all the backend auth logic. Phase 09 is primarily UI work wrapping the Supabase JS client. The existing `supabase.ts` client and `auth.tsx` context are the foundation — they work today.

### Sign Up

**Screen:** `SignUpScreen` at route `/signup`

**Supabase method:** `supabase.auth.signUp({ email, password })`

**Fields:**
- Email (type="email", required, autocomplete="email")
- Password (type="password", required, min 8 chars, autocomplete="new-password")
- Confirm Password (client-side match validation only — Supabase doesn't expose confirm)

**Validation:**
- Email: valid format (browser native + custom check)
- Password: minimum 8 characters, show strength indicator (simple: red/yellow/green)
- Confirm password: must match password field before submit enabled

**Error states:**
- "An account with this email already exists." (Supabase: `User already registered`)
- "Password is too weak." (Supabase: password requirements if enabled)
- Network errors: "Something went wrong. Please try again."

**Success behaviour:**
- If Supabase email confirmation is enabled: show confirmation pending screen ("Check your inbox — we've sent a confirmation link to {email}. Click it to activate your account.")
- If email confirmation is disabled (recommended for closed MVP with known users): redirect to `/onboarding`

**Note on email confirmation:** For a 2-person closed MVP, disabling email confirmation in Supabase dashboard is simpler and reduces friction. Trinity should decide. If enabled, a `ConfirmPendingScreen` is needed.

**Link from Login:** "Don't have an account? Sign up." below the login form.

---

### Log In

**Screen:** `LoginScreen` (already exists at `/login`) — needs enhancement:

**Current gaps to fill:**
- Add "Forgot your password?" link below the password field (→ `/forgot-password`)
- Add "Don't have an account? Sign up" link (→ `/signup`)

**Supabase method:** `supabase.auth.signInWithPassword({ email, password })` — already implemented.

**Error states (enhance from current):**
- "Invalid email or password." (map Supabase's generic "Invalid login credentials")
- "Email not confirmed. Please check your inbox." (if confirmation is enabled)

**Success redirect logic (new):**
- After successful login, check if user has ≥1 active Source
- If no Sources: `navigate('/onboarding')`
- If Sources exist: `navigate('/')`

This check runs in `handleSubmit` after `signInWithPassword` succeeds. Query `GET /sources?limit=1` — if empty list, redirect to onboarding.

---

### Forgot Password

**Screen:** `ForgotPasswordScreen` at route `/forgot-password`

**Supabase method:** `supabase.auth.resetPasswordForEmail(email, { redirectTo: '<app-url>/reset-password' })`

**Fields:**
- Email (type="email", required)

**Behaviour:**
- Always show success message regardless of whether email exists (prevents account enumeration)
- Message: "If an account exists for {email}, you'll receive a reset link shortly."
- Return to login link: "Back to sign in"

**Error states:**
- Only network errors (show generic retry message)

---

### Reset Password

**Screen:** `ResetPasswordScreen` at route `/reset-password`

Supabase sends the user to this URL with a token in the URL hash. Supabase JS client handles extracting and validating the token via `onAuthStateChange` — when the user lands on this page, they are temporarily in a `PASSWORD_RECOVERY` session.

**Supabase method:** `supabase.auth.updateUser({ password: newPassword })`

**Fields:**
- New password (type="password", required, min 8 chars)
- Confirm new password

**Behaviour:**
- On mount, check that `supabase.auth.getSession()` returns a `PASSWORD_RECOVERY` event session. If not (stale/expired link), show: "This reset link has expired. Please request a new one." with a link back to `/forgot-password`.
- On success: redirect to `/` (or `/onboarding` if no Sources yet)

**Error states:**
- "Passwords do not match." (client-side)
- "Reset link has expired." (Supabase `invalid_claim` error)

---

### Email Verification

**If enabled in Supabase dashboard:**

Add an `onAuthStateChange` listener in `auth.tsx` that fires on `EMAIL_CONFIRMATION` event and redirects to `/onboarding`.

Add a `ConfirmPendingScreen` shown after signup explaining they should check their email.

Add an email verification success route: `/auth/confirm` that the Supabase confirmation link redirects to — this can simply call `supabase.auth.exchangeCodeForSession()` and navigate to `/onboarding`.

**If disabled (recommended for closed MVP):** no additional work.

---

### Log Out

**Component:** `AccountButton` or nav header menu (existing nav already likely has a logout trigger).

**Supabase method:** `supabase.auth.signOut()` — already in `auth.tsx:signOut`.

**Behaviour:**
- On success: redirect to `/login`
- Clear any local state (React Query cache, etc.)

**The existing `signOut` in `auth.tsx` already calls `supabase.auth.signOut()` and sets `session = null`. The redirect to `/login` is handled by `AuthGuard` — when session is null, it redirects to `/login`. No change needed to `auth.tsx`, only ensure a nav-level logout button exists.**

---

## 4. Onboarding Wizard Design

The wizard lives at `/onboarding`. It is a single-page multi-step flow. Steps are tracked in local component state (no URL per step — simpler, avoids deep-link concerns for MVP). Progress is shown as a step indicator (e.g., dots or "Step 2 of 5").

**Tone guidance (from Product Principles Brief):**
- Calm and honest. Never oversell. Acknowledge what Rippled will and won't do.
- Frame each step around the user's cognitive benefit, not the technical integration.
- Skip should feel easy and guilt-free, not like abandoning something important.
- No AI hype language. No "revolutionary." No "never forget anything again."

---

### Step 1: Welcome / Intent Screen

**Route:** `/onboarding` (step=1 in state)
**Component:** `OnboardingWelcome`

**Purpose:** Orient the user. Explain what Rippled does and what they're about to set up. Set honest expectations before asking for any credentials.

**Copy:**

> **Welcome to Rippled.**
>
> Rippled quietly watches your work communication — email, Slack, and meeting transcripts — and notices the commitments inside them.
>
> Things like "I'll send that over", "Let me follow up", "We'll have this by Friday." The promises that are easy to make and easy to forget.
>
> Once you connect your signals, Rippled will surface what looks like it needs attention. It won't tell you what to do. It will help you notice what you might have missed.
>
> This takes about 5 minutes to set up.

**CTA:** "Let's set up your signals →"

**Note:** No skip on this step. It is not optional — it is orientation.

---

### Step 2: Email Setup

**Route:** `/onboarding` (step=2 in state)
**Component:** `OnboardingEmail`

**"Why this matters" copy:**

> **Email is where a lot of commitments live — and where a lot of them get lost.**
>
> Rippled will monitor your inbox and sent mail for commitment signals: replies you promised, follow-ups you haven't sent, threads that are waiting on you.
>
> It looks at what you sent, not just what you received. Sent mail is often the strongest evidence that a commitment was made — or delivered.
>
> Rippled uses IMAP — a standard protocol supported by Gmail, Outlook, and iCloud. You'll provide your email address and an app password (not your main account password).

**Form fields:**
- Email address (pre-filled if they signed up with an email — ask "Is this the mailbox you want to connect?" with option to use a different one)
- IMAP server (default populated based on email domain detection: gmail → `imap.gmail.com`, outlook → `imap-mail.outlook.com`, icloud → `imap.mail.me.com`)
- IMAP port (default 993, rarely needs changing)
- App password / password (type="password")
- Sent folder name (default "Sent", advanced — collapsed by default under "Advanced options")
- Internal domains (comma-separated — "What email domains belong to your organisation? e.g., yourdomain.com" — help Rippled tell internal vs external participants apart. Optional for MVP — can skip.)

**Provider-specific hints:**

Show contextual guidance based on email domain:
- Gmail: "Gmail requires an App Password, not your account password. Go to myaccount.google.com → Security → 2-Step Verification → App passwords."
- Outlook/Microsoft: "Go to account.microsoft.com → Security → Advanced security options → App passwords."
- iCloud: "Go to appleid.apple.com → Sign-In and Security → App-Specific Passwords."
- Other: Show generic IMAP instructions.

**Connection test:**

Before saving, show a "Test connection" button that calls `POST /sources/test/email` with the entered credentials. Returns:
- Success: "Connected to {email} — {N} messages found in INBOX." Green checkmark.
- Failure: "Could not connect. Check your credentials and try again." With specific error: "Authentication failed", "Server not found", "SSL error".

**On save:** POST to a new `POST /sources/setup/email` endpoint that stores credentials in `Source.credentials` (encrypted). Sets `display_name = email address`, `provider_account_id = email address`.

**What is written to the database:**

`Source` record:
```json
{
  "user_id": "<user_id>",
  "source_type": "email",
  "provider_account_id": "kevin@example.com",
  "display_name": "kevin@example.com",
  "is_active": true,
  "credentials": {
    "imap_host": "imap.gmail.com",
    "imap_port": 993,
    "imap_user": "kevin@example.com",
    "imap_password": "<encrypted>",
    "imap_ssl": true,
    "imap_sent_folder": "Sent",
    "internal_domains": "example.com"
  }
}
```

**Skip behaviour:** "Skip for now — I'll connect email later" link below the form. Skip writes no Source record. The user can return via `/settings/sources`.

**Completion state:** Green banner at top of step: "Email connected — kevin@example.com". CTA changes to "Continue →".

---

### Step 3: Slack Setup

**Route:** `/onboarding` (step=3 in state)
**Component:** `OnboardingSlack`

**"Why this matters" copy:**

> **A lot of small commitments are made in Slack.**
>
> "I'll check on that." "Sending it now." "I'll get back to you by EOD." These pass through conversation quickly and rarely make it anywhere permanent.
>
> Rippled connects to your Slack workspace using a bot token. It reads messages in channels and DMs you invite it to, and surfaces commitments it finds there.
>
> It does not read everything by default. You choose which channels.

**Setup method for MVP: Manual Slack bot token (not OAuth)**

OAuth for Slack requires a publicly accessible redirect URL and Slack app approval — this adds deployment complexity not justified for a 2-user MVP. The manual path:

1. User creates a Slack App at api.slack.com/apps
2. Configures Event Subscriptions → Request URL → `https://{deployment-url}/api/v1/webhooks/slack/events`
3. Subscribes to bot events: `message.channels`, `message.im`, `message.groups`
4. Under OAuth & Permissions, adds scopes: `channels:history`, `groups:history`, `im:history`, `mpim:history`, `users:read`
5. Installs to workspace → copies Bot User OAuth Token
6. Copies Signing Secret from Basic Information

The onboarding UI provides step-by-step instructions with screenshots placeholders and links to Slack dashboard.

**Form fields:**
- Bot token (xoxb-... — type="password" display)
- Signing secret
- Slack User ID ("Your Slack user ID — we use this to identify messages from you. You can find it in your Slack profile → More → Copy member ID.")
- Workspace ID (auto-detected from token verification, or paste manually)

**Connection test:**

`POST /sources/test/slack` — takes bot token, calls Slack `auth.test` API endpoint. Returns:
- Success: "Connected to workspace '{workspace_name}' as @{bot_user}." Green checkmark.
- Failure: "Token invalid or expired. Check your bot token."

**On save:** POST to `POST /sources/setup/slack`. Stores credentials in `Source.credentials`.

**What is written to the database:**

`Source` record:
```json
{
  "user_id": "<user_id>",
  "source_type": "slack",
  "provider_account_id": "T0XXXXXX",
  "display_name": "My Workspace",
  "is_active": true,
  "credentials": {
    "bot_token": "<encrypted>",
    "signing_secret": "<encrypted>",
    "team_id": "T0XXXXXX",
    "user_id": "U0XXXXXX"
  }
}
```

**Skip behaviour:** "Skip for now — I'll connect Slack later." Slack is likely to be the most friction-heavy step for non-technical users; skip is important.

---

### Step 4: Meeting Transcripts

**Route:** `/onboarding` (step=4 in state)
**Component:** `OnboardingMeetings`

**"Why this matters" copy:**

> **Meetings are where big promises get made — and where they quietly disappear.**
>
> Rippled reads meeting transcripts to find commitments made across speaker turns. "We'll send the proposal by Thursday." "I'll follow up with the team." "Let's schedule a review."
>
> It does not record or transcribe your meetings. It reads transcripts that your meeting tool already produces, using a webhook.
>
> You choose your platform. Rippled generates a webhook URL you configure there.

**Platform picker:**
- Fireflies.ai
- Otter.ai
- Read.ai
- Manual / Custom

Each selection shows platform-specific setup instructions (see Section 5 below).

**Common to all platforms:**

The wizard generates a webhook secret and shows:
- **Webhook URL:** `https://{deployment-url}/api/v1/webhooks/meetings/transcript`
- **Webhook secret:** `{generated-secret}` (copy button)

These are stored in the meeting Source's metadata/credentials.

**On save:** POST to `POST /sources/setup/meeting`. Creates Source record with `source_type = "meeting"`, `provider_account_id = platform name`.

**What is written to the database:**

`Source` record:
```json
{
  "user_id": "<user_id>",
  "source_type": "meeting",
  "provider_account_id": "fireflies",
  "display_name": "Fireflies.ai",
  "is_active": true,
  "credentials": {
    "webhook_secret": "<generated-secret>",
    "platform": "fireflies"
  }
}
```

**Skip behaviour:** "Skip for now — I'll connect meetings later." Prominent — meeting setup is the most technically involved step.

---

### Step 5: Done / First Run Screen

**Route:** `/onboarding` (step=5 in state)
**Component:** `OnboardingComplete`

**Content:**

> **Rippled is now listening.**
>
> {summary of what was connected, e.g.:}
> - Email connected: kevin@example.com
> - Slack connected: My Workspace
> - Meetings: Fireflies.ai
>
> {OR if nothing was connected:}
> - No signals connected yet. You can set them up in Settings → Sources.
>
> ---
>
> **Here's what happens next.**
>
> Rippled will start processing your communication in the background. Within the next few minutes, it will begin ingesting messages and detecting commitments.
>
> You'll see them appear on your dashboard as they're found. It won't surface everything at once — it looks for signals that seem to matter, and it waits before interrupting you with lower-confidence items.
>
> **The first run takes a little time.** If your inbox is large, it may take a while to process everything. That's normal.
>
> ---
>
> **A few things Rippled will and won't do:**
> - It will notice things it thinks are commitments. It's often right. Sometimes it's not.
> - It will preserve uncertainty rather than guess. You'll see "likely" and "seems" — that's intentional.
> - It won't send emails on your behalf, assign tasks, or make decisions.

**CTA:** "Go to dashboard →" → `/`

Mark onboarding complete by setting a flag (see Section 8).

---

## 5. Platform-Specific Setup Guides

### Fireflies.ai

**Webhook support:** Yes — Fireflies has native webhook support for meeting transcripts. This is the cleanest integration for MVP.

**Setup instructions for wizard:**

1. Log in to app.fireflies.ai
2. Go to Settings → Integrations → Webhooks
3. Click "Add webhook"
4. Paste the webhook URL: `https://{deployment-url}/api/v1/webhooks/meetings/transcript`
5. For the secret/authentication: Fireflies supports a custom header. Enter header name `X-Rippled-Webhook-Secret` and the generated secret value.
6. Subscribe to event: `Transcription completed`
7. Save.

**Fireflies webhook payload:** Fireflies sends a JSON payload with `meetingId`, `title`, `organizer_email`, `transcript` (as text or structured sentences). The meeting connector normaliser handles this — it already expects a structured format. **Note:** Fireflies' native webhook format differs from the `MeetingTranscriptPayload` schema. Phase 09 should add a Fireflies-specific normaliser shim that translates the Fireflies payload format into the standard internal format before ingesting.

**Reliability:** High. Fireflies is the most webhook-ready meeting platform for this use case.

---

### Otter.ai

**Webhook support:** Limited. As of knowledge cutoff, Otter.ai does not offer a native developer webhook API for transcript delivery. It has a closed ecosystem — no public API for programmatic transcript export on standard plans.

**What's practical for MVP:**

Option A — Manual paste: User copies the transcript text from Otter's UI and pastes it into a simple form at `/settings/sources/meeting/manual`. Rippled wraps it as a transcript payload and ingests. High friction, not automated.

Option B — Otter.ai Zapier integration: Otter can trigger a Zap on meeting completion. The Zap sends a webhook to Rippled's meeting endpoint. This works but requires the user to set up a Zapier account and workflow. Adds a third-party dependency.

**Recommendation:** For MVP, be honest in the wizard:

> **Otter.ai**
>
> Otter doesn't currently offer a direct webhook integration. To connect Otter, you can:
>
> - Use our Zapier template to forward transcripts automatically (requires a Zapier account)
> - Or paste transcripts manually using our import tool
>
> We'll add native Otter support when their API becomes available.

---

### Read.ai

**Webhook support:** Read.ai has an API and supports webhook notifications on meeting completion (available on Pro/Enterprise plans). Their webhook includes meeting summary, transcripts, and action items.

**Setup instructions for wizard:**

1. Log in to app.read.ai
2. Go to Settings → Integrations → Webhooks
3. Add a new webhook endpoint: `https://{deployment-url}/api/v1/webhooks/meetings/transcript`
4. Select event: `meeting.completed`
5. Set the shared secret to your generated Rippled webhook secret
6. Save.

**Read.ai webhook payload:** Read.ai sends a different schema than Fireflies. It includes a `transcript` array with speaker-attributed segments. Again, a Read.ai-specific normaliser shim is needed.

**Important caveat:** Read.ai webhook access may require a paid plan. Be honest in the wizard:

> **Read.ai**
>
> Read.ai supports webhooks on paid plans. If you're on a free plan, you'll need to upgrade or use manual import.

**Reliability:** Medium — plan dependency, but the integration is technically clean when available.

---

### Manual / Custom

For users with their own meeting tools, custom scripts, or platforms not listed:

**What to provide in the wizard:**

> **Manual / Custom webhook**
>
> Any tool that can send an HTTP POST can forward transcripts to Rippled.
>
> **Webhook URL:** `https://{deployment-url}/api/v1/webhooks/meetings/transcript`
>
> **Authentication:** Include a header `X-Rippled-Webhook-Secret: {your-secret}`
>
> **Expected JSON format:**
> ```json
> {
>   "meeting_id": "unique-meeting-id",
>   "meeting_title": "Weekly Sync",
>   "started_at": "2026-03-13T10:00:00Z",
>   "ended_at": "2026-03-13T11:00:00Z",
>   "participants": [
>     {"name": "Kevin", "email": "kevin@example.com"},
>     {"name": "Mitch", "email": "mitch@example.com"}
>   ],
>   "segments": [
>     {
>       "speaker": "Kevin",
>       "text": "I'll follow up on that by Friday.",
>       "start_seconds": 123.4,
>       "end_seconds": 127.1
>     }
>   ]
> }
> ```

This schema matches the existing `MeetingTranscriptPayload` in `app/connectors/meeting/schemas.py`.

---

**MVP decision for platform normalisers:** Phase 09 should build Fireflies shim normaliser as a real integration, add Read.ai shim as a second real integration, and treat Otter as manual for now. All platform shims sit in `app/connectors/meeting/platform_normalizers/` and are called based on the Source's `credentials["platform"]` field.

---

## 6. Backend Changes Required

### app/connectors/email/imap_poller.py

**Current:** `poll_new_messages(user_id: str)` reads credentials from global `get_settings()`.

**Changes:**
- Remove `user_id` parameter from `poll_new_messages` — it now iterates all email Sources
- Fetch all active email Sources with `credentials IS NOT NULL`
- For each Source, extract credentials and decrypt them
- Call `_poll_source(source_id, source.user_id, creds)` per source
- Internal `_poll_source` replaces the current monolithic body — same IMAP logic, but takes explicit credential params instead of reading globals
- Keep env var fallback for Sources without credentials (backward compat, log warning)

### app/connectors/slack/tasks.py (or app/tasks.py)

**Changes:**
- `process_slack_event(payload: dict)` currently resolves `user_id` from `SLACK_USER_ID` global env var
- New: extract `team_id` from event payload (`payload.get("team_id")` or `payload["event"].get("team")`)
- Query Source where `source_type = "slack"` and `provider_account_id = team_id`
- Load `user_id` from `source.user_id`, `signing_secret` from decrypted credentials

### app/api/routes/webhooks/slack.py

**Changes:**
- Currently verifies with global `SLACK_SIGNING_SECRET`
- New: extract `team_id` from raw body (the JSON payload — available before HMAC is verified since it's in the body, not the headers)
- Look up Slack Source by team_id, get signing secret from credentials
- Fall back to global `SLACK_SIGNING_SECRET` if no Source found (for development)
- **Important:** The request body is read as bytes before JSON parsing (already the case for HMAC). Parse JSON for `team_id` lookup, but keep bytes for HMAC.

### app/connectors/shared/credentials_utils.py (NEW)

New file:
```python
from cryptography.fernet import Fernet
from app.core.config import get_settings

def _get_cipher() -> Fernet:
    """Derive Fernet cipher from SECRET_KEY."""
    ...

def encrypt_credentials(data: dict) -> dict:
    """Encrypt sensitive fields in credentials dict."""
    SENSITIVE_FIELDS = {"imap_password", "bot_token", "signing_secret", "webhook_secret"}
    result = dict(data)
    for key in SENSITIVE_FIELDS:
        if key in result and result[key]:
            result[key] = _encrypt(result[key])
    result["_encrypted"] = True
    return result

def decrypt_credentials(data: dict) -> dict:
    """Decrypt sensitive fields from credentials dict."""
    ...
```

### app/core/config.py

**No removal yet** — keep all existing env vars for backward compat during the transition. After both users complete onboarding and credentials are in the DB, the connector-specific env vars can be removed. Document this in Phase 09 decisions.

### app/api/routes/sources.py

**Changes:**
- `create_source` endpoint currently does NOT accept or save `credentials` (line 25-35). Add a `credentials` field to `SourceCreate` schema — accepted optionally, encrypted before storage.
- `update_source` currently doesn't accept `credentials`. Add optional `credentials` update support.

**New endpoints:**

**`POST /sources/setup/email`**
A higher-level endpoint for the wizard. Takes email IMAP credentials, validates them (attempt connection), then creates or updates the email Source. Returns the Source or validation error.

```
Request body:
{
  "email": "kevin@example.com",
  "imap_host": "imap.gmail.com",
  "imap_port": 993,
  "imap_password": "app-password",
  "imap_ssl": true,
  "imap_sent_folder": "Sent",
  "internal_domains": "example.com"
}
```

**`POST /sources/setup/slack`**
Takes Slack bot token, signing secret, user_id. Validates token via Slack API. Creates or updates Slack Source.

**`POST /sources/setup/meeting`**
Takes platform name. Generates a webhook secret. Creates meeting Source with generated secret.

**`POST /sources/test/email`**
Test IMAP connection without saving credentials. Returns connection result and basic mailbox stats.

```
Request: { imap_host, imap_port, imap_user, imap_password, imap_ssl }
Response: { success: true, message: "Connected to kevin@example.com (1,234 messages in INBOX)" }
       OR { success: false, error: "Authentication failed", detail: "..." }
```

**`POST /sources/test/slack`**
Test Slack bot token without saving. Calls Slack `auth.test`. Returns workspace name.

```
Request: { bot_token: "xoxb-..." }
Response: { success: true, workspace: "My Workspace", bot_user: "@rippled-bot" }
       OR { success: false, error: "Invalid token" }
```

### app/connectors/meeting/platform_normalizers/ (NEW)

New package with:
- `fireflies.py` — translates Fireflies webhook payload to `MeetingTranscriptPayload`
- `read_ai.py` — translates Read.ai webhook payload to `MeetingTranscriptPayload`

The meeting webhook handler dispatches to the correct normaliser based on Source's `credentials["platform"]`.

### app/api/routes/sources.py — onboarding state endpoint

**`GET /sources/onboarding-status`**
Returns whether the user has completed onboarding (used by frontend redirect logic):
```json
{
  "has_sources": true,
  "sources": [
    {"source_type": "email", "display_name": "kevin@example.com", "is_active": true},
    {"source_type": "slack", "display_name": "My Workspace", "is_active": true}
  ]
}
```

---

## 7. Frontend Changes Required

### New screens

| Screen | Route | Purpose |
|---|---|---|
| `SignUpScreen` | `/signup` | Email + password signup form |
| `ForgotPasswordScreen` | `/forgot-password` | Email entry for reset link |
| `ResetPasswordScreen` | `/reset-password` | New password entry after clicking reset link |
| `OnboardingScreen` | `/onboarding` | Multi-step wizard (all 5 steps in one screen component) |
| `SourcesSettingsScreen` | `/settings/sources` | Manage connected sources after onboarding |
| `AccountSettingsScreen` | `/settings/account` | Change password, log out |

### Updates to existing files

**`App.tsx`:**
- Add routes for all new screens
- Add `/onboarding` route (guarded by AuthGuard — user must be logged in)
- Add `/settings/*` routes
- Auth routes (`/signup`, `/forgot-password`, `/reset-password`) are NOT guarded — accessible without login

**`LoginScreen.tsx`:**
- Add "Forgot password?" link → `/forgot-password`
- Add "Don't have an account? Sign up" link → `/signup`
- Change success redirect: check onboarding status, redirect to `/onboarding` or `/`

**`auth.tsx`:**
- Add `signUp(email, password)` method to `AuthContextValue`
- Add `onboarding_complete` flag tracking (via `supabase.auth.updateUser({ data: { onboarding_complete: true } })` — Supabase user metadata)
- Or: determine onboarding state from API call to `GET /sources/onboarding-status`

**Navigation / Header component:**
- Add user menu with "Account settings" → `/settings/account`
- Ensure logout is accessible from the nav

### Post-login redirect logic

The redirect decision after login (or on app load for an already-authenticated user):

```typescript
// In App.tsx or a dedicated hook
async function getPostAuthRoute(): Promise<string> {
  const response = await api.get('/sources/onboarding-status')
  return response.data.has_sources ? '/' : '/onboarding'
}
```

This check runs:
1. After successful `signInWithPassword`
2. After email confirmation redirect
3. On `AuthGuard` mount when session already exists (on refresh)

**Important:** The redirect from `AuthGuard` should NOT unconditionally go to `/` — it should go to the result of `getPostAuthRoute()`. This is a change from current behaviour.

### SourcesSettingsScreen

Shows all connected sources in a list. For each:
- Source type icon, display name, connection status
- "Disconnect" button (soft delete — sets `is_active = false`)
- "Reconnect / Edit" button — opens the relevant wizard step in a modal or navigates to `/settings/sources/email`

Also shows a "Connect new source" section for any source type not yet connected.

### AccountSettingsScreen

- Change password form (`supabase.auth.updateUser({ password: newPassword })`)
- Current email (read-only — Supabase email change is complex, defer for MVP)
- Sign out button

---

## 8. Onboarding State

**How the app knows if a user has completed onboarding:**

The cleanest signal: `GET /sources` returns at least one active Source record.

- Has ≥1 Source → user has completed at least partial onboarding → go to Dashboard
- Has 0 Sources → user has not connected anything → go to Onboarding

**Alternative: Supabase user metadata flag**

`supabase.auth.updateUser({ data: { onboarding_complete: true } })` sets a field in Supabase's `raw_user_meta_data` JSONB. This can be read from the session's `user.user_metadata.onboarding_complete` without an API call.

**Recommendation: Use both.**

Use the Supabase metadata flag as the fast check (no API call needed, already in session). Set it when the user clicks "Go to dashboard" on the onboarding completion screen. On login, if `user.user_metadata.onboarding_complete === true`, go straight to Dashboard. If `false` or unset, call `GET /sources/onboarding-status` to double-check (handles edge case where onboarding was partially done or the flag wasn't set).

**Where the check lives:**

In a `useOnboardingRedirect` hook, called by:
- `App.tsx` `AuthGuard` component on mount
- `LoginScreen.tsx` after successful login
- `ResetPasswordScreen.tsx` after successful password update

The hook:
```typescript
async function useOnboardingRedirect(session: Session | null) {
  if (!session) return
  const meta = session.user.user_metadata
  if (meta?.onboarding_complete) {
    navigate('/')
    return
  }
  const { data } = await api.get('/sources/onboarding-status')
  navigate(data.has_sources ? '/' : '/onboarding')
}
```

**Re-entering onboarding:** A user who has Sources can still navigate to `/onboarding` manually (e.g., to add a new source type). The wizard handles this gracefully: if a source type is already connected, the step shows its connection status and offers "Edit" or "Skip" as the primary action.

---

## 9. Open Questions for Trinity

### Q1: Email confirmation — enable or disable for MVP?

**Question:** Supabase email confirmation requires users to click a link before their account is active. For a known 2-person MVP (Kevin + Mitch), this adds friction. Should we enable or disable it?

**Recommendation: Disable for MVP.**

With two known invited users, email confirmation serves no security purpose — Kevin and Mitch are expected users. Disabling removes an unnecessary friction step and eliminates the need for `ConfirmPendingScreen` and email confirmation handling. It can be re-enabled when the product opens to broader access.

**If Trinity wants to keep it enabled:** The build adds a `ConfirmPendingScreen` and a `/auth/confirm` exchange route. About 1 day additional work.

---

### Q2: Credentials encryption — implement now or defer to post-MVP?

**Question:** Encrypting `Source.credentials` adds 40–60 lines and a new dependency (`cryptography`). For a closed 2-user MVP on private infrastructure, is this necessary now?

**Recommendation: Implement now.**

The `cryptography` package is already likely installed (common FastAPI dependency). The implementation is small. The alternative — plaintext IMAP passwords and Slack bot tokens in the database — is the kind of thing that silently becomes a problem when the system scales or a database dump is shared for debugging. The investment is minimal relative to the risk.

**If Trinity wants to defer:** Mark `credentials` as plaintext with a `TODO: encrypt` comment and a note in `decisions.md`. Implement in a pre-launch security pass. Accept the risk for a private 2-user beta.

---

### Q3: Slack setup — manual bot token or OAuth?

**Question:** Manual Slack bot setup (user creates app, pastes tokens) is low friction for developer users but high friction for non-technical users like Mitch. Slack OAuth would be smoother UX but requires a publicly accessible redirect URL and Slack app configuration at the deployment level (one Slack app for all users).

**Recommendation: Manual bot token for MVP.**

For a 2-user private MVP, OAuth overhead is not justified. Kevin and Mitch are both capable of following the setup steps. The wizard provides step-by-step instructions with links. If Rippled ever opens to general users, a proper OAuth integration should be built — but that is a separate phase.

**If Trinity wants OAuth:** The build adds a Slack OAuth flow with a `GET /auth/slack/callback` endpoint and redirect handling. Adds ~1 day and requires deploying with a stable public URL first. Consider this post-MVP.

---

### Q4: Where should `internal_domains` live — per-email-source or per-user?

**Question:** `internal_domains` is used to classify whether a message participant is internal or external. Currently it is a global env var. Should it be:
- A) Stored in the email Source's credentials (per-source)
- B) Stored in the User model as a profile setting (per-user, shared across all sources)

**Recommendation: Per email Source credentials (option A) for MVP.**

It is most naturally associated with "I have this email account and these are my organisation's domains." Storing it with the Source is the path of least resistance and doesn't require schema changes to the User model. A user with multiple email accounts from different organisations could theoretically have different domain lists — per-source handles this correctly.

---

### Q5: Should the onboarding wizard enforce at least one connected source before allowing dashboard access?

**Question:** If a user skips all three source steps and clicks "Go to dashboard," Rippled has nothing to observe. Should we:
- A) Allow skipping all steps and show an empty dashboard with a "Connect your first source" prompt
- B) Require at least one source to be connected before leaving onboarding

**Recommendation: Option A — allow full skip.**

Forcing credential entry before first dashboard access creates anxiety. A user should be able to see the product before committing credentials. The dashboard with zero sources shows a helpful empty state: "Rippled has no signals yet. Connect your first source to get started." with links to settings. This is more respectful of the user's pace.

---

### Q6: How should meeting webhook secrets be generated and displayed?

**Question:** When a user configures a meeting source, we generate a webhook secret for them. Should this secret be:
- A) Generated server-side on `POST /sources/setup/meeting` and shown once (user copies it immediately)
- B) Let the user generate their own secret (input field) and we store/validate it

**Recommendation: Server-side generation (option A).**

Generated secrets are cryptographically random and correctly formatted. User-provided secrets may be weak or reused. Show the secret once at the end of the meeting setup step with a prominent "Copy secret — you won't see this again" warning. Store the encrypted secret in `Source.credentials["webhook_secret"]`.

If the user loses the secret, they can regenerate it via `POST /sources/{id}/regenerate-secret` (a new endpoint). We should build this alongside the setup endpoint.

---

## 10. Test Strategy

### Backend tests

**Connection test endpoints:**

| Test file | Tests | Focus |
|---|---|---|
| `tests/api/test_source_test_endpoints.py` | 10–12 | IMAP test: success, auth failure, host not found, SSL error. Slack test: valid token, invalid token, API error. Input validation. |
| `tests/connectors/test_credentials_utils.py` | 6–8 | Encrypt → decrypt roundtrip for each sensitive field. Non-sensitive fields pass through unmodified. Empty credentials. Legacy plaintext detection. |
| `tests/api/test_source_setup_endpoints.py` | 8–10 | Email setup: creates Source with encrypted credentials, returns Source. Slack setup: validates token (mocked), creates Source. Meeting setup: generates secret, creates Source. Update existing source (idempotent upsert). |
| `tests/connectors/test_imap_poller_multiuser.py` | 6–8 | Poll iterates all active email Sources. Uses per-source credentials. Skips Sources with no credentials (with fallback log). Handles one Source failing without crashing others. |

**Auth flow tests:**

| Test file | Tests | Focus |
|---|---|---|
| `tests/api/test_onboarding_status.py` | 4–5 | Zero sources → `has_sources: false`. One source → `has_sources: true`. Inactive source → not counted. Unauthenticated → 401. |

### Frontend tests

Frontend testing is lighter — Rippled uses no frontend test suite yet. For Phase 09:

- Manual test script for the full wizard flow (document in `build/phases/09-onboarding/manual-test-plan.md`)
- Key flows to manually verify: signup → onboarding → connect email (with test connection) → connect Slack → skip meetings → dashboard. Login → forget password → reset → login again. Second user (Mitch) signup → independent credentials.

### Target test count

Backend: ~34–43 new tests
Frontend: manual verification (no automated frontend tests in current codebase)

### Regression bar

```bash
pytest tests/ -q          # all prior tests must remain green
ruff check app/            # no new lint violations
```

---

## 11. Confidence & Blockers

**Confidence: High on scope. Medium on some specifics.**

**High confidence areas:**
- Auth flows — Supabase SDK handles all backend logic; this is UI scaffolding around a proven library
- Source.credentials schema — well-defined, the column already exists
- Onboarding wizard flow — the UX is clear; implementation is standard React form handling
- `imap_poller` refactor — the change is contained and the logic is already well-understood
- Connection test endpoints — IMAP connection testing is straightforward; Slack `auth.test` is a one-liner

**Medium confidence areas:**
- Fireflies webhook payload format — the interpretation assumes Fireflies sends a parseable JSON payload with transcript content. This should be verified against Fireflies' live documentation before building the normaliser. The schema in their documentation may differ from what their webhooks actually send.
- Read.ai webhook format — same caveat. Read.ai's webhook schema needs live verification.
- Slack multi-workspace credential routing — the change to per-Source signing secrets requires the webhook endpoint to do a DB lookup before HMAC verification. This needs careful sequencing (read body as bytes → find source by team_id → verify HMAC) to avoid security gaps.

**Blockers:**
- **Deployment URL needed for Slack and meeting webhook setup.** The wizard shows the user a webhook URL they paste into external platforms. This must be a stable, publicly accessible URL. If the deployment isn't live yet, this step cannot be completed during local development without ngrok or similar.
- **Supabase email confirmation setting.** Trinity needs to decide this (Q1 above) before the signup flow can be implemented completely.
- **SECRET_KEY suitable for Fernet.** Fernet requires a 32-byte URL-safe base64 key. The existing `SECRET_KEY` env var may not be in this format. Either convert it or add a `ENCRYPTION_KEY` env var. Needs checking.

**Dependencies:**
- Phases 01–08 complete — yes, per git log
- `Source.credentials` JSONB column exists — confirmed (orm.py:48)
- Supabase JS client available — confirmed (supabase.ts)
- Auth context established — confirmed (auth.tsx)
- Existing routes use `get_current_user_id` dependency — confirmed — new endpoints follow the same pattern

**Timeline estimate:** Not provided per CLAUDE.md guidelines. The scope is well-defined and the paths are clear.

---

*Interpretation written: 2026-03-13*
