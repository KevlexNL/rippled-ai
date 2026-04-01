# Rippled — Automated Test Spec
**Last run:** 2026-03-31 (DB audit only — debug endpoint not yet built)
**Config:** `~/projects/rippled-ai/`
**Golden dataset:** `docs/golden-dataset-spec.md`

> 🤖 Automated pipeline tests require WO-RIPPLED-PIPELINE-DEBUG-ENDPOINT to be deployed.
> Until then: DB-level audits and API health checks can run. Signal-level stage tests pending.

---

## Known Issues (update after each run)

| ID | Feature | Severity | Issue | Status | First seen |
|----|---------|----------|-------|--------|------------|
| RI-KI-001 | Signal eligibility | `[CRITICAL]` | Marketing/bulk emails bypassing Stage 0 — fragments promoted as commitments | 🔧 WO-RIPPLED-EMAIL-ELIGIBILITY-FILTER pending Trinity | 2026-03-31 |
| RI-KI-002 | Routing — obligation_marker | `[CRITICAL]` | 247 candidates stuck — never promote or discard (routing logic broken for this trigger class) | Open | 2026-03-31 |
| RI-KI-003 | Routing — follow_up_commitment | `[CRITICAL]` | 204/248 candidates stuck — inconsistent promotion logic | Open | 2026-03-31 |
| RI-KI-004 | Surfacing | `[CRITICAL]` | 346 commitments in 0.6–0.8 confidence, none surfaced — surfacing threshold or logic broken | Open | 2026-03-31 |
| RI-KI-005 | Stage 3 extraction | `[HIGH]` | Fragments (4–5 chars: "done", "well.", "We'll") passing extraction and being promoted | 🔧 Partially addressed by RI-KI-001 fix | 2026-03-31 |
| RI-KI-006 | Timestamp | `[MEDIUM]` | All commitments showing "Today" — ingestion timestamp used instead of signal timestamp | ✅ Fixed — WO-RIPPLED-SIGNAL-LINK-MISSING | 2026-03-31 |
| RI-KI-007 | Stage 3 extraction | `[MEDIUM]` | Marketing CTAs ("let me be direct", "let me know if...") classified as explicit_self_commitment | Open | 2026-03-31 |

---

## Feature Registry

### RI-F01 — Stage 0: Eligibility Filter
**Purpose:** Reject signals before any LLM call — bulk emails, noreply senders, empty content, unsupported sources.
**Architecture principle:** Script-first filter. No LLM cost for junk signals.
**Golden signals:** GD-E06 (must reject), GD-E10 (must reject), GD-E01 (must pass), GD-E15 (must reject)
**Coverage gap noted in 2026-03-31 code review:** repo has normalization/timestamp tests and a suppressed-sender integration test, but no explicit automated case in the repo or this QA spec for header-based newsletter detection regressions tied to RI-KI-001.
**Test (once debug endpoint live):**
- GD-E06 → stage_0.eligible=false, reason=bulk_email
- GD-E10 → stage_0.eligible=false
- GD-E15 → stage_0.eligible=false (noreply sender)
- GD-E01 → stage_0.eligible=true
**Additional regression cases to add when debug endpoint is live:**
- Email with `List-Unsubscribe` header and normal-looking sender/domain → stage_0.eligible=false, reason=bulk_email
- Email with marketing headers (`X-Mailchimp-*`, `Precedence: bulk`, or similar bulk marker) but conversational body text → stage_0.eligible=false
- Email with `Auto-Submitted: auto-generated` or `auto-replied` and commitment-like phrasing → stage_0.eligible=false, reason=bulk_email or machine_generated
- Human reply forwarded through a marketing platform but with direct reply headers and a real sender → does **not** get rejected solely for ESP infrastructure; require combined bulk evidence
- Empty/near-empty body after quote stripping → stage_0.eligible=false, reason=insufficient_content
- Quoted newsletter thread containing an apparent commitment in older quoted text, but no new authored commitment in the latest block → stage_0.eligible=false
**DB audit test (available now):**
```sql
-- Count of bulk emails that slipped through (should be 0 after fix)
SELECT COUNT(*) FROM commitment_candidates cc
JOIN source_items si ON cc.originating_item_id = si.id
WHERE si.sender_email ILIKE '%newsletter%' OR si.sender_email ILIKE '%noreply%';
```

---

### RI-F02 — Stage 1: Candidate Gate
**Purpose:** First LLM call — cheap model decides if the signal even contains a commitment candidate.
**Golden signals:** GD-E07 (must reject), GD-E08 (must reject), GD-E09 (must reject), GD-E01 (must pass)
**Test:**
- GD-E07 ("done.") → candidate_present=false
- GD-E08 (marketing "let me be direct") → candidate_present=false
- GD-E09 ("must approve it in advance.") → candidate_present=false (missing context)
- GD-E01 ("I'll get you the contract by Friday") → candidate_present=true, trigger=explicit_self_commitment
- GD-E11 ("I'll try...") → candidate_present=true, confidence=0.65±0.1
**DB audit test:**
```sql
-- Fragments that made it past (should be 0 after fix)
SELECT raw_text, trigger_class FROM commitment_candidates
WHERE length(raw_text) < 10 AND was_promoted = true;
```

---

### RI-F03 — Stage 2: Speech Act Classification
**Purpose:** Classify the type of speech act — promise, request, obligation, delivery signal, etc.
**Golden signals:** GD-E01 (promise), GD-E02 (request), GD-E18 (delivery_signal), GD-E05 (deadline_change)
**Test:**
- GD-E01 → speech_act=promise, confidence≥0.80
- GD-E02 → speech_act=request, owner_resolution=recipient
- GD-E18 → speech_act=delivery_signal
- GD-E05 → speech_act=deadline_change

---

### RI-F04 — Stage 3: Commitment Extraction
**Purpose:** Extract structured fields — owner, deliverable, timing, target, confidence per field.
**Golden signals:** GD-E01, GD-E03, GD-E04, GD-E11, GD-E12, GD-E13, GD-E16
**Test per field:**

**Owner resolution:**
- GD-E01 (inbound) → owner_resolution=sender ✓
- GD-E03 (Kevin outbound) → owner_resolution=sender (Kevin) ✓
- GD-E04 ("We need to...") → ownership_ambiguity=HIGH ✓
- GD-E12 ("Matt said he'll...") → owner_resolution=third_party ✓

**Timing extraction:**
- GD-E01 ("by Friday") → timing_text="by Friday", timing_ambiguity=MEDIUM (no exact date)
- GD-E05 ("March 15th") → resolved_deadline=March 15, timing_ambiguity=NONE
- GD-E16 ("Wednesday March 30th at 5pm EST") → timing_ambiguity=NONE, timing_confidence≥0.95
- GD-E17 ("sometime soon") → timing_ambiguity=HIGH

**Deliverable extraction:**
- GD-E01 → deliverable_text="contract" or "send you the contract"
- GD-E02 → deliverable_text="event location and date"

---

### RI-F05 — Stage 4: Routing
**Purpose:** Deterministic routing based on stage outputs — promote, discard, observe, escalate.
**Known issue:** obligation_marker and follow_up_commitment routing is broken (RI-KI-002, RI-KI-003)
**Golden signals:** GD-E01 (promote), GD-E07 (discard), GD-E17 (observe)
**Test:**
- GD-E01 → action=promote
- GD-E07 → action=discard (fragment)
- GD-E17 ("sometime soon") → action=observe
**DB audit test:**
```sql
-- How many candidates are stuck? (should decrease over time as routing is fixed)
SELECT trigger_class, COUNT(*) FROM commitment_candidates
WHERE was_promoted = false AND was_discarded = false
GROUP BY trigger_class ORDER BY count DESC;
```

---

### RI-F06 — Confidence Scoring
**Purpose:** Each promoted commitment has 6 confidence dimensions. These drive surfacing decisions.
**Golden signals:** GD-E16 (all high), GD-E17 (all low), GD-E04 (ownership low, others medium)
**Test:**
- GD-E16 → confidence_commitment≥0.90, confidence_owner≥0.90, confidence_deadline≥0.95
- GD-E17 → confidence_commitment≤0.45, not surfaced
- GD-E04 → confidence_owner≤0.55 (ambiguous "we")
**DB audit:**
```sql
-- Distribution of confidence scores (healthy spread expected)
SELECT 
  ROUND(confidence_for_surfacing::numeric, 1) as bucket, 
  COUNT(*) 
FROM commitments GROUP BY bucket ORDER BY bucket;
```

---

### RI-F07 — Surfacing Logic
**Purpose:** Decide which commitments to show the user, when, and in what order.
**Known issue:** ZERO commitments surfaced — 346 stuck in 0.6–0.8 (RI-KI-004)
**Test:**
- GD-E16 after promotion → is_surfaced=true within reasonable time
- GD-E17 after promotion → is_surfaced=false (below threshold)
**DB audit:**
```sql
-- Surfacing rate (should be >0 after fix)
SELECT 
  COUNT(*) as total,
  SUM(CASE WHEN is_surfaced THEN 1 ELSE 0 END) as surfaced,
  ROUND(100.0 * SUM(CASE WHEN is_surfaced THEN 1 ELSE 0 END) / COUNT(*), 1) as pct
FROM commitments;
```

---

### RI-F08 — Signal Timestamps
**Purpose:** Commitments should display the original signal time, not ingestion time.
**Known issue:** All showing "Today" (RI-KI-006)
**Test:**
- Submit GD-E01 with a backdate → commitment.signal_timestamp matches input, not NOW()
- UI shows original date, not ingestion date
**Additional regression cases to add:**
- Email normalization preserves RFC822 `Date` / provider event time into `source_item.occurred_at` and `signal_timestamp`
- Slack/meeting-derived signals preserve source event timestamp through promotion into commitment display fields
- Mixed-timezone input (e.g. EST source) renders as the correct absolute time after UTC normalization

---

### RI-F09 — Entity / People Extraction
**Purpose:** Identify who is involved — owner, requester, beneficiary, counterparty. Resolve against known contacts.
**Golden signals:** GD-E14 (named sender), GD-E12 (third party)
**Test:**
- GD-E14 (Samantha Katchen) → counterparty_name="Samantha Katchen", counterparty_email="sam@krsinsurance.com"
- GD-E12 ("Matt said...") → requester_resolved=sender, beneficiary_name=Kevin

---

### RI-F10 — UI: Commitment List & Review
**Purpose:** User sees surfaced commitments, can review/skip/confirm.
**Coverage gap noted in 2026-03-31 code review:** backend/service tests exist for surfacing and API skip actions, but the repo review did not show matching frontend/E2E review-flow coverage for list interactions in this QA spec.
**Test (browser, when debug UI exists):**
- Surfaced commitments appear in list view
- Status badges correct (needs_review, confirmed, dormant)
- Skip / confirm / snooze actions work
- Timestamp shows original signal date (not ingestion)
- List ordering matches surfacing priority / score expectations
- Empty state renders correctly when surfacing count is zero
- Skip action removes or re-labels the item immediately without requiring full page refresh
- Confirm action persists across reload and updates the visible status badge/state
- Snooze action hides the item from the default queue until the snooze window expires
- Mixed queue state test: one skipped, one confirmed, one still needs review → counts and visible filters stay consistent

---

### RI-F11 — Email Eligibility Script Filter (new)
**Purpose:** Script-based pre-filter before any LLM — rejects bulk/marketing emails via headers/sender patterns.
**Status:** WO pending Trinity
**Test:**
- Email with List-Unsubscribe header → rejected at Stage 0, reason=bulk_email
- Email from noreply@* → rejected, reason=noreply_sender
- Email from Mailchimp (X-Mailchimp-* headers) → rejected, reason=marketing_tool
- Legitimate reply email → passes
- Email with bulk marker plus quoted human commitment in thread history → rejected before LLM; quoted text must not rescue newsletter
- Email with benign sender but `Auto-Submitted: auto-generated` / equivalent machine-generated marker → rejected
- Email with genuine human sender, no bulk headers, and explicit commitment sentence → passes even if it contains CTA-like phrases such as `let me know`
**DB audit after fix:**
```sql
-- Verify no new marketing emails in candidates
SELECT si.sender_email, COUNT(*) FROM commitment_candidates cc
JOIN source_items si ON cc.originating_item_id = si.id
WHERE cc.created_at > NOW() - INTERVAL '24 hours'
AND (si.sender_email ILIKE '%newsletter%' OR si.sender_email ILIKE '%noreply%')
GROUP BY si.sender_email;
```

---

## How to Run Tests

### DB audit (available now, no debug endpoint needed)
```bash
cd ~/projects/rippled-ai
DB_URL=$(railway variables --json | python3 -c "import json,sys,urllib.parse; d=json.load(sys.stdin); print(urllib.parse.unquote(d.get('DATABASE_URL','')))")
python3 -c "
import psycopg2
conn = psycopg2.connect('$DB_URL')
# run audit queries from each feature above
"
```

### Pipeline signal tests (requires debug endpoint — WO-RIPPLED-PIPELINE-DEBUG-ENDPOINT)
```bash
BASE_URL=https://rippled.railway.app  # or local
TOKEN=<admin_token>

curl -s -X POST $BASE_URL/api/v1/debug/pipeline \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_type":"email","text":"I will get you the contract by Friday.","sender_name":"John","direction":"inbound","is_external":true}'
```

### Full run checklist
1. DB audit queries for RI-F01 through RI-F11 (available now)
2. For each RI-KI-xxx open issue: rerun the relevant audit query, update status if fixed
3. Once debug endpoint live: feed GD-E01 through GD-E18 through pipeline, compare to golden dataset labels
4. Update Known Issues table
5. Update "Last run" timestamp

---

## Reset / Clean State

No reset needed for read-only DB audit tests.
For signal-level tests via debug endpoint: dry_run=true, no DB writes.
