# Phase D2 — User-Configurable Auto-Close Timing

**Phase:** D2-auto-close-config
**Date:** 2026-04-01
**Status:** QUEUED
**Brief References:** Brief 10 (Completion Detection)

---

## Goal

Make the auto-close inactivity window user-configurable. Currently, after a commitment moves to `delivered`, Rippled uses system-default timing to decide when to auto-close it (move to `closed`). Brief 10 specifies this should be "a user-configurable inactivity period following likely delivery." This phase adds that configurability, allowing users to tune how long delivered commitments wait before auto-closing, with separate settings for internal vs external commitments.

---

## Scope (what's included)

- New `auto_close_config` JSONB column on `user_settings` table storing auto-close timing overrides
- Alembic migration adding the column
- Config schema supporting separate internal/external windows and optional per-commitment-class overrides (big_promise vs small_commitment)
- Modify `apply_auto_close()` in `app/services/completion/updater.py` to respect user config
- Modify the Celery auto-close sweep task to load user settings before processing
- API endpoint additions: extend `PATCH /api/v1/user/settings` to accept auto-close config
- Extend `GET /api/v1/user/settings` to return current auto-close config (merged defaults + overrides)
- Validation: windows must be positive, between 1 hour and 30 days
- Frontend settings UI: add auto-close configuration section

---

## Out of Scope

- Per-commitment manual auto-close overrides (bulk config only, not per-item)
- Disabling auto-close entirely (delivered items must eventually close; minimum 1 hour)
- Changing the delivery threshold logic (that stays as-is from Phase 05)
- Auto-close for non-delivered states

---

## Technical Approach

**Database:**
Add `auto_close_config` JSONB column to `user_settings`. Schema:
```json
{
  "internal_hours": 48,
  "external_hours": 120,
  "big_promise_hours": 168,
  "small_commitment_hours": 48
}
```
All values in hours. NULL = use system defaults. The resolution order: commitment-class-specific > internal/external > system default.

**Service layer:**
Modify `apply_auto_close()` in `completion/updater.py` to accept an optional config dict. Current logic checks `delivered_at + inactivity_window < now`; the change is making `inactivity_window` configurable rather than hardcoded.

Add a helper `get_auto_close_hours(commitment, user_config=None) -> float` that resolves the correct window based on commitment class and internal/external status, falling back through the hierarchy.

**Celery sweep:**
The auto-close sweep task in `app/tasks.py` loads user settings for each user being processed and passes config to the updater.

**API:**
Extend `UserSettingsPatch` and `UserSettingsRead` in `app/api/routes/user_settings.py`.

**Frontend:**
Add "Auto-Close Timing" section to settings page with inputs for internal/external and optionally big/small commitment windows.

---

## Success Criteria

- [ ] User can configure auto-close windows via `PATCH /api/v1/user/settings`
- [ ] Delivered commitments respect user-configured inactivity window before auto-closing
- [ ] External commitments default to longer auto-close window than internal (per Brief 10)
- [ ] Big promises can have longer auto-close windows than small commitments
- [ ] Auto-close remains reversible (closed -> active transition still works)
- [ ] Invalid values rejected with 422
- [ ] Frontend settings page shows and allows editing auto-close durations
- [ ] Existing auto-close tests continue to pass
- [ ] New tests: custom config respected, partial config merges, class-specific override works, validation

---

## Files Likely Affected

- `app/models/orm.py` — `UserSettings` model (new column)
- `app/services/completion/updater.py` — configurable auto-close logic
- `app/tasks.py` — auto-close sweep loads user settings
- `app/api/routes/user_settings.py` — extend Pydantic models + endpoint
- `alembic/versions/` — new migration
- `frontend/src/` — settings page component
- `tests/services/test_completion_updater.py` — new + updated tests

---

## Dependencies

- None strictly, but D1 (observation windows) should ideally go first since both modify `user_settings` and the settings API. Doing D1 first establishes the pattern for JSONB config columns on `user_settings`.

---

## Estimated Effort

1-2 days. The auto-close logic is contained in `completion/updater.py`. The main work is adding the config resolution hierarchy and threading user settings through the sweep task, plus frontend UI.

---

## Brief References

**Brief 10 — Completion Detection:**
> "Allow closure after a user-configurable inactivity period following likely delivery." (Section: Auto-close behavior)

> "external/client-facing delivery: close after X days without contrary signal" / "internal delivery: close after a shorter or user-defined window" (Section: Auto-close behavior, MVP default)

> "auto-close should be configurable and reversible" (Section: Default MVP rules)

Brief 10 explicitly calls out that auto-close timing is a user-configurable setting, not a permanent system default. The current hardcoded behavior was documented as "MVP defaults, not permanent truths."
