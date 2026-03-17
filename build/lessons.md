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

---

### 2026-03-17 — LLM JSON responses wrapped in markdown code fences
**Mistake:** `json.loads()` was called directly on raw LLM response text. LLMs frequently wrap JSON in `` ```json ... ``` `` code fences even when instructed to return "valid JSON only". The `JSONDecodeError` was caught silently (returned `[]`), making the failure invisible — 178 items processed, 0 commitments, 0 errors.
**Pattern:** Always strip markdown code fences from LLM responses before JSON parsing. Never rely on prompt instructions alone to control LLM output format. When catching parse errors, log at WARNING level with the raw response snippet so silent failures are detectable.
**Severity:** Critical

---

### 2026-03-17 — Zero-item judge run triggers false WO
**Mistake:** LLM judge threshold check `avg_quality < 3.5` fires when `items_reviewed == 0` because `avg_quality` defaults to 0. This creates a prompt improvement WO with zero data — no suggestions, no sample failures, nothing actionable.
**Pattern:** When aggregating metrics for threshold-based alerts, always guard against the zero-denominator case. An empty result set is not a quality failure — it's a no-op. Add `items_reviewed > 0` guard before threshold checks.
**Severity:** Minor

---

### 2026-03-17 — Suppression regex character class matches newlines
**Mistake:** Greeting suppression pattern used `[^.]` (negated character class), which matches any character except literal period — including newlines. This caused multi-line suppression, wiping out commitment text on subsequent lines.
**Pattern:** In multiline regex patterns, always use `[^.\n]` instead of `[^.]` when the intent is to match within a single line. Also limit greedy quantifiers with `{0,N}` to prevent suppression patterns from consuming content that contains actual signals.
**Severity:** Medium
