# Phase 09 — Onboarding, Account Management & Multi-User: Complete

**Completed:** 2026-03-13

## Auth flows built
- SignUpScreen.tsx — email + password + confirm, Supabase signUp(), redirects to /onboarding
- ForgotPasswordScreen.tsx — resetPasswordForEmail(), success state with email instructions
- ResetPasswordScreen.tsx — updateUser({password}), redirects to /
- LoginScreen.tsx — updated with "Forgot password?" + "Sign up" links, post-login onboarding check

## Onboarding wizard built
- OnboardingScreen.tsx — 5-step wizard:
  - Step 0: Welcome
  - Step 1: Email setup (IMAP auto-detect, connection test, save)
  - Step 2: Slack setup (bot token, signing secret, test, save)
  - Step 3: Meeting transcripts (platform picker, webhook generation)
  - Step 4: Done (connected sources summary, sets onboarding_complete metadata)

## Settings screens built
- SourcesSettingsScreen.tsx — list/disconnect/add sources at /settings/sources
- AccountSettingsScreen.tsx — password change, email display, sign out at /settings/account

## Backend changes made
- app/connectors/shared/credentials_utils.py — Fernet encryption for imap_password, bot_token, signing_secret, webhook_secret
- app/core/config.py — ENCRYPTION_KEY, base_url env vars added
- app/models/schemas.py — SourceRead has has_credentials (no raw creds), request schemas added
- app/api/routes/sources.py — 7 new endpoints: test/email, test/slack, setup/email, setup/slack, setup/meeting, regenerate-secret, onboarding-status
- app/connectors/email/imap_poller.py — multi-user: poll_all_email_sources(), per-source credentials with env var fallback
- app/connectors/slack/normalizer.py — accepts slack_user_id parameter
- app/api/routes/webhooks/slack.py — per-source signing_secret lookup by team_id
- app/tasks.py — process_slack_event uses per-source lookup, poll_email_imap calls poll_all_email_sources()

## Test count
- tests/connectors/test_credentials_utils.py: 8 tests
- tests/api/test_source_setup_endpoints.py: 8 tests
- tests/api/test_source_test_endpoints.py: 6 tests
- tests/api/test_onboarding_status.py: 5 tests
- tests/connectors/test_imap_poller_multiuser.py: 6 tests
- Total new tests: 33
- Total test suite: 357 passing

## New env vars
- ENCRYPTION_KEY — optional; if set, credentials are Fernet-encrypted at rest. If unset, plaintext stored with warning log.
- BASE_URL — optional; used for meeting webhook URL generation (e.g. https://api.rippled.ai)

## Decisions made during implementation
- Email confirmation disabled in Supabase for MVP (per Q1)
- ENCRYPTION_KEY uses SHA-256 derivation to produce valid 32-byte Fernet key from any string
- Meeting webhook_secret only generated on source creation; use POST /sources/{id}/regenerate-secret for rotation
- Slack team_id lookup happens before HMAC verification (documented as accepted MVP tradeoff in build/lessons.md)
- SourcesSettingsScreen uses GET /api/v1/sources (not onboarding-status) to get source IDs for disconnect
