# Lessons Learned

Track patterns from corrections to avoid repeating mistakes.

## Format
```
### [DATE] — Short title
**Mistake:** What went wrong
**Pattern:** The rule to follow going forward
**Severity:** Minor / Medium / Critical
```

---

### 2026-03-13 — Slack team_id oracle: pre-verification DB lookup creates timing side-channel
**Mistake:** Looking up a per-source signing secret by team_id before verifying the request signature means an unauthenticated caller can probe whether a team_id is registered by observing response timing (DB hit vs. skip).
**Pattern:** When per-tenant secret lookup must happen before auth (unavoidable for HMAC bootstrap), document it explicitly as an accepted tradeoff and note it for hardening (e.g., constant-time response, rate-limiting, or moving secret resolution to a separate verified step). Never leave silent security tradeoffs undocumented.
**Severity:** Minor
