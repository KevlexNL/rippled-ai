# Active Work Orders

Work Trinity is currently executing or queued to pick up next.

---

## Queue (in priority order)

| WO | Title | Priority | Status |
|----|-------|----------|--------|
| WO-RIPPLED-NORMALIZED-SIGNAL-CONTRACT | Shared NormalizedSignal contract | CRITICAL | PENDING |
| WO-RIPPLED-EMAIL-QUOTED-TEXT-STRIPPING | Strip quoted history from email | HIGH | PENDING |
| WO-RIPPLED-SPEECH-ACT-CLASSIFICATION | Add speech_act to detection | HIGH | PENDING |
| WO-RIPPLED-REQUESTER-BENEFICIARY-FIELDS | Add requester + beneficiary | MEDIUM | PENDING |
| WO-RIPPLED-LIFECYCLE-STATE-ALIGNMENT | Add missing lifecycle states | MEDIUM | PENDING |
| WO-RIPPLED-ARCH-DIAGRAM-TAB | Admin architecture diagram tab | MEDIUM | PENDING |
| WO-RIPPLED-DASHBOARD-ONBOARDING | Onboarding tour (?onboard=true) | MEDIUM | PENDING |
| WO-RIPPLED-REVIEW-FIXES | UX fixes from Kevin's first review | HIGH | PENDING |
| WO-RIPPLED-USER-IDENTITY-PROFILE | User identity profile system | CRITICAL | COMPLETE |
| WO-RIPPLED-SKIP-STATE | Skip action on commitment review | LOW | COMPLETE |

---

## Recently Completed

- **User Identity Profile** — `user_identity_profiles` table, fuzzy matching, onboarding screen, Settings → Identity tab. 99/261 commitments resolved to Kevin's user.
- **surfacing_audit user_id** — Added `user_id` column to surfacing_audit, backfilled 64 rows.
- **Skip action** — Skip button on commitment cards, `skipped_at` DB field, filtered from review queue.
- **Dormant lifecycle state** — "Not Now" button, dormant state in DB, show/hide toggle.
- **List filtering** — Default view shows mine + triage, others behind "View all →".
- **Prompt v4** — Greeting exclusions, bare follow-up patterns, user_relationship, structure_complete.

---

!!! tip "How to request work"
    Post in [GitHub Discussions](https://github.com/KevlexNL/rippled-ai/discussions) and Mero will create a Work Order.
