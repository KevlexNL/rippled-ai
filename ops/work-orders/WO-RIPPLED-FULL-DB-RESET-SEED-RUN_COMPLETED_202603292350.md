# WO-RIPPLED-FULL-DB-RESET-SEED-RUN

**Status:** PENDING
**Priority:** High (run after Slack WOs complete)
**Owner:** Trinity
**Created:** 2026-03-29
**Scope:** Rippled — clean database reset + comprehensive re-seed

---

## Objective

Clear the entire Rippled database and perform a comprehensive re-seed run using all integrated channels (email, meetings, Slack), leveraging all architectural changes from the foundational WOs. The goal is a clean, fully structured dataset that reflects the current detection pipeline, lifecycle states, and signal processing logic.

---

## Context

The current database was seeded before the following foundational changes were made:
- `WO-RIPPLED-NORMALIZED-SIGNAL-CONTRACT` — new signal schema
- `WO-RIPPLED-EMAIL-QUOTED-TEXT-STRIPPING` — cleaner email bodies
- `WO-RIPPLED-SPEECH-ACT-CLASSIFICATION` — proper speech act tagging
- `WO-RIPPLED-REQUESTER-BENEFICIARY-FIELDS` — requester/beneficiary fields
- `WO-RIPPLED-LIFECYCLE-STATE-ALIGNMENT` — correct lifecycle states
- `WO-RIPPLED-LLM-ORCHESTRATION` — staged pipeline
- `WO-RIPPLED-SLACK-CONNECTOR-BUILD` — Slack ingestion
- `WO-RIPPLED-MEETING-NORMALIZER-UPDATE` — improved meeting normalization
- `WO-RIPPLED-SLACK-THREAD-ENRICHMENT` — thread context
- `WO-RIPPLED-SLACK-SPECIFIC-PROMPT-OVERLAY` — Slack prompt overlay

The existing data is stale and was processed by older, less accurate pipeline versions. A clean re-seed is required to get a trustworthy dataset for Kevin to test and validate.

---

## Pre-conditions (ALL must be complete before this WO starts)

- [ ] `WO-RIPPLED-SLACK-THREAD-ENRICHMENT` complete
- [ ] `WO-RIPPLED-SLACK-SPECIFIC-PROMPT-OVERLAY` complete
- [ ] `WO-RIPPLED-CANDIDATE-PROMOTION-BROKEN` complete
- [ ] `WO-RIPPLED-DETECTION-RESCAN-LOOP` complete

**Do not start this WO until all four are complete.**

---

## Phases

### Phase 1 — Pre-Reset Backup
- Dump current DB to `ops/backups/pre-reset-YYYY-MM-DD.sql`
- Commit the backup path (not the file) to git as a reference
- Log current stats: source item count, commitment count, candidate count

### Phase 2 — Database Reset
- Truncate all tables in correct dependency order (preserve schema, drop data only):
  - `surfacing_audit`
  - `candidate_signal_records`
  - `signal_processing_stage_runs`
  - `signal_processing_runs`
  - `commitments`
  - `normalized_signals`
  - `source_items` (keep raw ingest records if possible)
- Reset all sequences
- Verify DB is empty before proceeding

### Phase 3 — Full Re-Seed Run
- Process all `source_items` in chronological order (oldest → newest)
- Run full normalization + detection pipeline for each source type:
  - Email (via `EmailNormalizationService`)
  - Meetings (via updated `MeetingNormalizerService`)
  - Slack (via `SlackConnector` + `ThreadEnricher` + `SlackPromptOverlay`)
- Process in day-by-day batches to avoid overwhelming the LLM API
- Log progress: items processed, commitments created, errors

### Phase 4 — Candidate Promotion
- After ingestion, run the candidate promotion pipeline
- Verify candidates are being promoted to commitments correctly
- Log: candidates created, promoted, held for triage

### Phase 5 — Validation
- Run post-seed validation checks:
  - Total commitments created
  - Commitments with `structure_complete = true` vs `false`
  - Distribution across lifecycle states
  - Distribution across source types (email / slack / meeting)
  - Any items stuck in `proposed` for > 7 days
- Write validation report to `ops/reports/post-reset-seed-YYYY-MM-DD.md`
- Notify Mero with summary

---

## Success Criteria

- [ ] DB fully cleared and re-seeded from scratch
- [ ] All source types processed (email, meeting, Slack)
- [ ] Candidate promotion running correctly
- [ ] Post-seed validation report written
- [ ] At least 50% of commitments have `structure_complete = true`
- [ ] No detection rescan loop active after seed
- [ ] Kevin notified with summary stats

---

## Files to Create

- `ops/backups/pre-reset-YYYY-MM-DD.sql` (backup reference)
- `ops/reports/post-reset-seed-YYYY-MM-DD.md` (validation report)
- `scripts/full_reseed.py` (re-usable seed script for future resets)

---

## Dependencies

- All Slack WOs complete (see pre-conditions above)
- LLM API rate limits: process in batches of 50 items/run, 2-min pause between batches

---

## Notify When Done

Mero + Kevin via Rippled Telegram group — include full stats summary
