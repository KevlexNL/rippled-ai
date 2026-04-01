# D1 — User-Configurable Observation Windows: Interpretation

**Phase:** D1-observation-windows
**Stage:** STAGE 2 — INTERPRET
**Date:** 2026-04-01

---

## 1. What This Phase Requires

Users currently have no control over how long Rippled silently observes a commitment before surfacing it. The observation window durations are hardcoded in two places:

- `app/services/observation_window.py` — `_DEFAULT_WINDOWS` dict (used by `default_window_hours()`, consumed by surfacing router via `is_observable()`)
- `app/services/detection/detector.py` — `_OBSERVE_HOURS` dict (used by `_compute_observe_until()`, which stamps `observe_until` on each CommitmentCandidate at detection time)

This phase adds a JSONB column to `user_settings` that stores per-source-type overrides, threads that config through the detection and surfacing pipelines, exposes it via the existing settings API, validates inputs, and adds a frontend UI for editing.

The key invariant: existing commitments with `observe_until` already set are NOT retroactively changed. Only new detections pick up the user's custom windows.

---

## 2. Current State of Affected Files

### `app/services/observation_window.py`
- Defines `_DEFAULT_WINDOWS` with 8 entries (slack, slack_internal, email, email_internal, email_external, meeting, meeting_internal, meeting_external) — all in calendar hours (working hours * 1.4).
- `default_window_hours(source_type, external)` → returns calendar hours. Uses exact match, then external variant, then partial match, then fallback of 33.6h.
- `is_observable(commitment)` → checks `observe_until` against now.
- `should_surface_early(commitment)` → bypass logic for high-consequence external promises.
- **No user config parameter exists anywhere** — purely static defaults.

### `app/services/detection/detector.py`
- Has its OWN separate `_OBSERVE_HOURS` dict (lines 41-45) with different values than `observation_window.py`! Slack=2h, email_internal=8h, email_external=48h, meeting_internal=16h, meeting_external=48h. These are raw calendar hours, NOT using the 1.4 multiplier.
- `_compute_observe_until(source_type, is_external)` → adds hours to `now()`.
- Called in two places: Tier 1 detection (line 236) and Tier 2 detection (line 322).
- **Does NOT import from `observation_window.py`** — this is a duplication issue.

### `app/services/surfacing_runner.py`
- `run_surfacing_sweep(db)` loads all active commitments and routes them.
- Does NOT call `default_window_hours()` directly — the surfacing router calls `is_observable()` which just checks the pre-stamped `observe_until` timestamp.
- **No user config loading here.** Surfacing doesn't need to know about window config — it only checks the already-computed `observe_until` on the commitment.

### `app/api/routes/user_settings.py`
- `GET /api/v1/user/settings` returns `UserSettingsRead` (digest_enabled, digest_to_email, google/anthropic/openai connection status).
- `PATCH /api/v1/user/settings` accepts `UserSettingsPatch` with digest and API key fields.
- Uses async SQLAlchemy sessions.

### `app/models/orm.py` — `UserSettings` (line 464)
- Table `user_settings`, PK = `user_id`.
- Fields: digest_enabled, digest_time, last_digest_sent_at, google tokens, LLM keys, is_super_admin, timestamps.
- **No `observation_window_config` column yet.**

### `app/tasks.py` — `detect_commitments` task (line 132)
- Takes `source_item_id`, opens a sync session, calls `run_detection(source_item_id, session)`.
- Does NOT load user settings or pass user config to detection.
- To thread user config through, this task needs to: load the SourceItem's `user_id`, fetch `UserSettings` for that user, extract `observation_window_config`, and pass it to `run_detection`.

### `frontend/src/api/userSettings.ts`
- TypeScript interfaces for `UserSettingsRead` and `UserSettingsPatch`.
- `getUserSettings()` / `patchUserSettings()` API calls.

### `frontend/src/screens/SettingsModal.tsx`
- Tabbed settings modal (General / Identity).
- General tab has LLM API Token section and Integrations section.
- No observation window UI exists.

### Tests
- **No `test_observation_window.py` exists.** Observation window logic is tested indirectly in detection and surfacing tests.
- Existing tests in `test_detection.py`, `test_surfacing.py`, `test_clarification.py` reference `observe_until`.

### Migrations
- Located in `migrations/versions/`, latest is `s3t4u5v6w7x8` (revises `r2s3t4u5v6w7`).
- Standard pattern: `op.execute()` for data migrations, `op.add_column()` / `op.drop_column()` for schema changes.

---

## 3. Implementation Plan

### Step 1: Migration — Add `observation_window_config` column
**File:** `migrations/versions/t4u5v6w7x8y9_add_observation_window_config.py`
- `op.add_column("user_settings", sa.Column("observation_window_config", JSONB, nullable=True))`
- NULL default = use system defaults (no data backfill needed).
- Downgrade: `op.drop_column("user_settings", "observation_window_config")`

### Step 2: ORM model — Add column to `UserSettings`
**File:** `app/models/orm.py`
- Add `observation_window_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)` to the `UserSettings` class.

### Step 3: Unify observation window defaults
**File:** `app/services/observation_window.py`
- Add `get_window_hours(source_type, external, user_config=None) -> float` that checks `user_config` dict first (using the JSONB key format: `slack`, `email_internal`, `email_external`, `meeting_internal`, `meeting_external`), then falls back to `_DEFAULT_WINDOWS`.
- Keep `default_window_hours()` as-is for backward compatibility (or refactor it to delegate to `get_window_hours` with `user_config=None`).
- Add `VALID_WINDOW_KEYS` constant for validation.
- Add `merge_with_defaults(user_config) -> dict` helper that returns the full config with defaults filled in (for GET endpoint).

### Step 4: Fix detector to use unified window function
**File:** `app/services/detection/detector.py`
- Remove the duplicated `_OBSERVE_HOURS` dict and `_compute_observe_until` function.
- Import `get_window_hours` from `observation_window.py`.
- Replace `_compute_observe_until(source_type, is_external)` with a new version that accepts `user_config=None` and delegates to `get_window_hours`.
- Update the two call sites (Tier 1 line 236, Tier 2 line 322) to pass user config.
- Modify `run_detection()` signature to accept `user_config: dict | None = None`.

### Step 5: Thread user config through the detection task
**File:** `app/tasks.py`
- In `detect_commitments`, after loading the SourceItem, query `UserSettings` for `item.user_id`.
- Extract `observation_window_config` (may be None).
- Pass it to `run_detection(source_item_id, session, user_config=user_config)`.

### Step 6: API — Extend Pydantic models and endpoint
**File:** `app/api/routes/user_settings.py`
- Add validation model `ObservationWindowConfig` with optional float fields for each source key, validated 0.5 <= value <= 168.
- Add `observation_window_config` to `UserSettingsRead` — returns merged defaults + overrides.
- Add `observation_window_config` to `UserSettingsPatch` — accepts partial overrides.
- Update `_to_read()` to merge user overrides with defaults.
- Update PATCH handler to validate and store the config.

### Step 7: Frontend TypeScript types
**File:** `frontend/src/api/userSettings.ts`
- Add `observation_window_config` to both `UserSettingsRead` and `UserSettingsPatch` interfaces.

### Step 8: Frontend UI — Observation Windows settings section
**File:** `frontend/src/screens/settings/ObservationWindowsSection.tsx` (new component)
- Section with 5 input fields (one per source key: Slack, Email Internal, Email External, Meeting Internal, Meeting External).
- Show current values from `settings.observation_window_config` (which already includes merged defaults from the API).
- Input validation: 0.5–168 hours.
- Display in user-friendly units: show hours for values < 24, show days + hours for values >= 24.
- Save button that PATCHes only the changed values.
- "Reset to defaults" button that sends null/empty config.

**File:** `frontend/src/screens/SettingsModal.tsx`
- Import and render `ObservationWindowsSection` in the General tab, between LLM API Token and Integrations sections.

### Step 9: Tests (TDD — these get written first in Stage 3)
**File:** `tests/services/test_observation_window.py` (new)
- `test_default_window_hours_returns_expected_defaults` — existing behavior preserved.
- `test_get_window_hours_user_config_overrides_default` — custom config takes precedence.
- `test_get_window_hours_partial_config_falls_back` — omitted keys use defaults.
- `test_merge_with_defaults_fills_missing_keys` — merge helper works correctly.

**File:** `tests/api/test_user_settings_observation.py` (new)
- `test_get_returns_merged_defaults` — GET with no user config returns all defaults.
- `test_patch_stores_valid_config` — PATCH with valid overrides stores them.
- `test_patch_rejects_out_of_range` — values < 0.5 or > 168 return 422.
- `test_patch_rejects_negative` — negative values return 422.
- `test_patch_null_resets_to_defaults` — sending null clears overrides.

**File:** `tests/services/test_detection.py` (additions)
- `test_detection_uses_user_config_for_observe_until` — custom window is reflected in `observe_until`.

---

## 4. Questions and Concerns

### Q1: Duplicate observation window values in detector.py
**Issue:** `detector.py` has its own `_OBSERVE_HOURS` with DIFFERENT values from `observation_window.py`'s `_DEFAULT_WINDOWS`. The detector uses raw hours (e.g., slack=2, email_internal=8), while `observation_window.py` uses working hours * 1.4 (e.g., slack=2.8, email_internal=33.6).

**Recommendation:** This is a pre-existing inconsistency. Unify both to use `observation_window.py` as the single source of truth. The `_DEFAULT_WINDOWS` values (with the 1.4 multiplier) match the brief's intent. This is a natural part of the refactor — the detector should import from `observation_window.py` rather than maintaining its own copy.

**Risk:** Changing the detector's window values will affect new commitments' `observe_until` timestamps. Existing commitments are unaffected (success criterion: "existing commitments with `observe_until` already set are not retroactively changed"). This is a correctness fix, not a behavior change — the detector values were always supposed to match the brief.

### Q2: Should the surfacing runner load user config?
**Analysis:** No. The surfacing runner checks `is_observable(commitment)`, which only examines the already-stamped `observe_until` datetime on the commitment. It doesn't need the window config — that config is consumed at detection time when `observe_until` is computed. The brief's mention of updating `surfacing_runner.py` may be unnecessary unless we want the surfacing sweep to re-derive window status from config (which would conflict with "existing commitments are not retroactively changed").

**Recommendation:** Leave `surfacing_runner.py` unchanged. The observation window config is consumed at detection time only.

### Q3: JSONB key format
The brief specifies keys: `slack`, `email_internal`, `email_external`, `meeting_internal`, `meeting_external`. This matches the `_DEFAULT_WINDOWS` keys in `observation_window.py` (minus the bare `email` and `meeting` aliases). Using 5 canonical keys is cleaner than exposing all 8 aliases.

**Recommendation:** Use exactly the 5 keys from the brief. The API validates only these keys.

### Q4: Working hours vs calendar hours in the UI
Users think in working hours ("2 working hours for Slack") but the stored values are calendar hours (2.8). The UI should display in the unit that's most intuitive.

**Recommendation:** Store as calendar hours (matching `_DEFAULT_WINDOWS`), but display in the UI with a label like "~2 working hours (2.8 calendar hours)" for the defaults. When users enter custom values, accept calendar hours with a helper note. This keeps the implementation simple and avoids a conversion layer.

### Q5: Frontend component approach
The brief says "sliders or input fields." The existing settings UI uses text inputs (for API keys) and simple toggle-style controls.

**Recommendation:** Use number input fields with step=0.5, consistent with the existing settings UI pattern. Sliders are harder to set precise values with and would be a UI pattern departure.

---

## 5. Complexity Assessment

**Brief estimate: 1–2 days.** I agree.

Breakdown:
- Migration + ORM: trivial (~15 min)
- Unify observation_window.py + add user config support: small (~30 min)
- Refactor detector.py to use unified function: small (~30 min, but needs care to not break existing tests)
- Thread config through tasks.py: small (~20 min)
- API model + endpoint changes: small (~30 min)
- Frontend section component: medium (~1–2 hours, new UI section with validation)
- Tests (written first per TDD): medium (~1–2 hours for the full test suite)
- Integration testing + edge cases: small (~30 min)

Total: ~5–7 hours of focused work = **1 day**, comfortably within the 1–2 day estimate.

The main risk is the detector.py refactor changing observation window durations for new detections (Q1 above), which needs explicit acknowledgment from Trinity.

---

## 6. Recommended Answers to Open Questions

| # | Question | Recommendation |
|---|----------|---------------|
| Q1 | Unify detector.py duplicated windows? | Yes — single source of truth in observation_window.py |
| Q2 | Update surfacing_runner.py? | No — it only reads pre-stamped observe_until |
| Q3 | JSONB key format? | 5 canonical keys from the brief |
| Q4 | UI display units? | Calendar hours with working-hour context labels |
| Q5 | Input type? | Number inputs, not sliders |

---

**Status:** Interpretation complete. Ready for Trinity review before proceeding to Stage 3 (BUILD).
