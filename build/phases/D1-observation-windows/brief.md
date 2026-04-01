# Phase D1 — User-Configurable Observation Windows

**Phase:** D1-observation-windows
**Date:** 2026-04-01
**Status:** QUEUED
**Brief References:** Brief 4 (Source Model), Brief 9 (Clarification)

---

## Goal

Allow users to configure per-source observation window durations instead of relying on hardcoded defaults. Observation windows control how long Rippled silently watches a commitment before surfacing it or requesting clarification. Currently these are hardcoded in `app/services/observation_window.py` (e.g., Slack 2 working hours, email 1-3 working days, meetings 1-3 working days). This phase makes them user-configurable while preserving the existing defaults as sensible fallbacks.

---

## Scope (what's included)

- New `observation_window_config` JSONB column on `user_settings` table storing per-source-type overrides
- Alembic migration adding the column with a NULL default (NULL = use system defaults)
- API endpoint additions: extend `PATCH /api/v1/user/settings` to accept observation window overrides
- Extend `GET /api/v1/user/settings` to return current observation window config (merged defaults + overrides)
- Modify `observation_window.py` to accept an optional user config dict and use it over hardcoded defaults
- Update `surfacing_runner.py` and any other callers of `default_window_hours()` to pass user config
- Update detection pipeline's `compute_observe_until()` to respect user config when available
- Validation: window values must be positive numbers within reasonable bounds (0.5 to 168 hours / 7 days)
- Frontend settings UI: add observation window configuration section to user settings page

---

## Out of Scope

- Per-commitment window overrides (this is per-source-type only)
- Working-hours-aware scheduling (keep the existing calendar-hour approximation)
- Per-sender or per-channel window customization
- Admin-level default overrides (this is user-level only)

---

## Technical Approach

**Database:**
Add `observation_window_config` JSONB column to `user_settings`. Schema:
```json
{
  "slack": 2.8,
  "email_internal": 33.6,
  "email_external": 67.2,
  "meeting_internal": 33.6,
  "meeting_external": 67.2
}
```
Values are calendar hours. Any key omitted falls back to system default.

**Service layer:**
Modify `default_window_hours(source_type, external, user_config=None)` in `observation_window.py` to check `user_config` first, then fall back to `_DEFAULT_WINDOWS`. This is a minimal change — the existing function signature gains one optional parameter.

**Detection pipeline:**
Update `compute_observe_until()` in `app/services/detection/detector.py` to accept and pass through user config. The Celery task loads user settings before calling detection.

**API:**
Extend `UserSettingsPatch` and `UserSettingsRead` Pydantic models in `app/api/routes/user_settings.py`.

**Frontend:**
Add a "Observation Windows" section to the settings page with sliders or input fields for each source type, showing current values (default or custom).

---

## Success Criteria

- [ ] User can set custom observation windows via `PATCH /api/v1/user/settings`
- [ ] Custom windows are respected by the surfacing pipeline (commitment surfaces after user-configured window, not hardcoded default)
- [ ] Omitted keys fall back to system defaults
- [ ] Invalid values (negative, zero, > 168 hours) are rejected with 422
- [ ] Existing commitments with `observe_until` already set are not retroactively changed
- [ ] Frontend settings page shows and allows editing observation window durations
- [ ] All existing observation window tests continue to pass
- [ ] New tests cover: custom config overrides default, partial config merges correctly, validation rejects bad input

---

## Files Likely Affected

- `app/models/orm.py` — `UserSettings` model (new column)
- `app/services/observation_window.py` — accept user config parameter
- `app/services/detection/detector.py` — pass user config to `compute_observe_until`
- `app/services/surfacing_runner.py` — load user config before observation check
- `app/api/routes/user_settings.py` — extend Pydantic models + endpoint
- `app/tasks.py` — load user settings in detection task
- `alembic/versions/` — new migration
- `frontend/src/` — settings page component
- `tests/services/test_observation_window.py` — new + updated tests

---

## Dependencies

- None — user settings infrastructure already exists from Phase C5

---

## Estimated Effort

1-2 days. The observation window logic is well-isolated in a single module. The main work is threading user config through the detection and surfacing pipelines, plus frontend UI.

---

## Brief References

**Brief 4 — Source Model:**
> "These defaults should be configurable later." (Section: Silent observation windows by source)

**Brief 9 — Clarification:**
> "provisional defaults and should be configurable later" (Section: Silent observation windows)

Both briefs explicitly defer observation window configurability to a post-MVP phase. The hardcoded defaults in `_DEFAULT_WINDOWS` map directly to the brief-specified values (Slack 2 working hours, email 1-3 working days, meetings 1-3 working days).
