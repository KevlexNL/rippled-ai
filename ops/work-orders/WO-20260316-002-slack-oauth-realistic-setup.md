# Work Order

## Title
Replace Slack custom-app setup with OAuth install flow for realistic DM + channel access

## Primary Type
Integration Readiness

## Priority
High

## Why This Matters
Slack is a first-wave source. The current custom-app configuration supports channel messages but cannot retrieve DMs — which is where a significant share of real commitments live. Until Slack uses a proper OAuth install flow with the correct scopes, commitment detection coverage from Slack is structurally incomplete and misleading for MVP testing.

## Problem Observed
- Current Slack source uses a bot token + signing secret (custom app, manually configured)
- Direct messages cannot be retrieved under this configuration
- No OAuth install flow exists in the app — users configure Slack by pasting a bot token manually
- This creates a false picture of Slack coverage in testing

## Desired Behavior
- Slack connection uses an OAuth install flow (user clicks "Connect Slack", authorizes via Slack's OAuth, token is stored automatically)
- Scopes include DM access: `im:history`, `im:read`, at minimum alongside `channels:history`, `channels:read`
- Existing Slack source for Kevin's account migrates or reconnects cleanly
- DMs appear as source_items alongside channel messages

## Relevant Product Truth
- Integration Readiness as a priority type in directive.md
- §8 MVP Source Priority: Slack is first-wave
- §12 What Good MVP Progress Looks Like: "integrations reflect realistic production-shaped setup, not misleading shortcuts"

## Scope
- Implement Slack OAuth install endpoint (Slack app settings → OAuth redirect)
- Request correct scopes for DM + channel history
- Store tokens via existing encrypted credentials model
- Update Slack connector to retrieve DMs via `conversations.list` (filter type=im) + `conversations.history`
- Update integration setup UI to show OAuth connect button instead of manual token entry
- Migrate or prompt reconnect for existing Slack sources

## Out of Scope
- Slack workspace-level distribution or Slack App Directory listing
- Slack slash commands or interactive components
- Slack notifications/webhooks outbound

## Constraints
- Requires Slack app to have redirect URL configured — needs Railway deploy URL
- DM access may require additional Slack app review for distribution (for now, internal use only is fine)
- Existing bot token for Kevlex Academy workspace should remain working until migration is confirmed

## Acceptance Criteria
- [ ] OAuth install flow works end-to-end: connect → authorize → token stored → source active
- [ ] DMs appear in source_items after ingestion run
- [ ] Channel messages continue to appear
- [ ] Integration setup UI shows OAuth button, not manual token paste

## Verification
- Browser test: connect Slack via OAuth flow, confirm redirect completes, source appears active
- DB query: `SELECT source_type, is_active FROM sources WHERE user_id = '441f9c1f...'`
- After ingest: `SELECT source_type, COUNT(*) FROM source_items GROUP BY source_type`
- At least some rows should be type=slack with DM thread_ids

## Escalate to Mero if
- Slack app OAuth redirect URL needs to be updated in Slack developer console (Kevin must do this)
- DM scope requires Slack app review that blocks internal testing

## Requires Approval
No — this is integration readiness work within the existing Slack source strategy.
