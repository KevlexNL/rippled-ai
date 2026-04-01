# Rippled — Golden Dataset Specification
**Created:** 2026-03-31
**Purpose:** Ground truth for pipeline testing. Each signal is labeled with expected output at every stage. Tests pass when pipeline output matches labels within tolerance.

---

## What the data revealed (2026-03-31 DB audit)

| Metric | Value |
|--------|-------|
| Total source_items | 1,564 (all email) |
| Total candidates | 842 |
| Promoted to commitments | 346 |
| Stuck (not promoted, not discarded) | 496 |
| Discarded | 0 |
| All commitments confidence | 0.6–0.8 (none surfaced) |

**Three confirmed bugs found in live data:**
1. **Fragments passing Candidate Gate** — "done", "well.", "We'll" (4–5 chars) promoted as commitments
2. **496 stuck candidates** — `obligation_marker` (247) and `follow_up_commitment` (248) never promote or discard — promotion logic broken for these trigger classes
3. **Zero surfaced** — 346 commitments all in 0.6–0.8 confidence bucket, none surfaced — surfacing threshold may be misconfigured or surfacing logic broken

---

## Signal Types to Cover

All current data is `email`. As other connectors come online, extend the dataset for each:
- `email` (current)
- `slack` (connector built, being tested)
- `meeting` (Read.ai connector)

---

## Golden Dataset: 25 Labeled Signals

### Email — Clear Commitments (should pass all stages, promote to commitment)

**GD-E01**
```
Source type: email
Sender: external (client/partner)
Direction: inbound
Text: "I'll get you the contract by Friday EOD."
```
Expected at each stage:
- Stage 0 (Eligibility): PASS — inbound, has content, real sender
- Stage 1 (Candidate Gate): candidate_present=true, trigger=explicit_self_commitment
- Stage 2 (Speech Act): promise/commitment, high confidence
- Stage 3 (Extraction): owner=sender, deliverable=contract, timing=Friday EOD
- Stage 4 (Routing): promote
- Commitment fields: resolved_owner=sender, vague_time_phrase=null (Friday EOD is concrete)

---

**GD-E02**
```
Source type: email
Sender: external
Direction: inbound
Text: "Can you send me the event location and date? Those details are included in the invite."
```
Expected:
- Stage 1: candidate_present=true, trigger=request_for_action
- Stage 3: owner=recipient (Kevin), deliverable=send event location/date, target=sender
- Commitment: requester=sender, owner=Kevin

---

**GD-E03**
```
Source type: email
Sender: Kevin (outbound)
Direction: outbound
Text: "I'll follow up with Ryan next week to nudge him on the outstanding items."
```
Expected:
- Stage 1: candidate_present=true, trigger=follow_up_commitment
- Stage 3: owner=Kevin, deliverable=follow up with Ryan, timing=next week
- Commitment: resolved_owner=Kevin, vague_time_phrase="next week"

---

**GD-E04**
```
Source type: email
Sender: external
Direction: inbound
Text: "We need to schedule a call before the end of the month to review the proposal."
```
Expected:
- Stage 1: trigger=explicit_collective_commitment or obligation_marker
- Stage 3: owner=ambiguous (we), timing=end of month
- Commitment: ownership_ambiguity=HIGH, timing_ambiguity=MEDIUM

---

**GD-E05**
```
Source type: email
Sender: external
Direction: inbound
Text: "The deadline has moved to March 15th. Please update your timeline accordingly."
```
Expected:
- Stage 1: trigger=deadline_change
- Stage 3: timing=March 15, owner=recipient, deliverable=update timeline
- Commitment: resolved_deadline=March 15, timing_ambiguity=NONE

---

### Email — Should NOT be commitments (must fail Candidate Gate or be discarded)

**GD-E06 — Marketing email (bulk sender)**
```
Source type: email
Sender: newsletter@substack.com
Headers: List-Unsubscribe present
Text: "actually afford AI tools now? The answer might surprise you."
```
Expected:
- Stage 0 (Eligibility): REJECT — bulk email, List-Unsubscribe header
- Should never reach Stage 1

---

**GD-E07 — Fragment from content splitter bug**
```
Source type: email
Text: "done."
Length: 4 characters
```
Expected:
- Stage 0 or Stage 1: REJECT — too short, not a commitment
- Currently FAILING: this is being promoted (GD-KNOWN-001)

---

**GD-E08 — Generic marketing CTA**
```
Source type: email
Sender: Mikael from Funnelytics
Text: "let me be direct... If you're in one of these 3 groups, this is probably the last rationally priced offer you'll see."
```
Expected:
- Stage 1: candidate_present=false OR discard — this is sales copy, not a commitment
- Currently FAILING: being promoted as explicit_self_commitment

---

**GD-E09 — Obligation marker that is NOT a personal commitment**
```
Source type: email
Text: "must approve it in advance."
```
Expected:
- Stage 1: candidate_present=false — missing context, not addressable as a commitment
- Currently FAILING: stuck as obligation_marker (GD-KNOWN-002)

---

**GD-E10 — Real estate newsletter**
```
Source type: email
Text: "need to be planning to buy anything to look at this. It's just a real example."
```
Expected:
- Stage 0: REJECT — bulk/newsletter email
- Stage 1 (if reaches it): candidate_present=false

---

### Email — Ambiguous / Edge cases (good for testing confidence calibration)

**GD-E11 — Soft commitment, low confidence**
```
Source type: email
Text: "I'll try to get that to you by Tuesday."
```
Expected:
- Stage 1: candidate_present=true, trigger=explicit_self_commitment
- Stage 3: owner=sender, timing=Tuesday, NOTE: "try" = hedged commitment
- Commitment: confidence_commitment=0.65 (lower than firm "I will"), vague_time_phrase="try to get that to you by Tuesday"

---

**GD-E12 — Third-party commitment**
```
Source type: email
Text: "Matt said he'll send the signed contract over by Thursday."
```
Expected:
- Stage 3: owner=Matt (third party), owner_resolution=third_party
- Commitment: ownership_ambiguity=MEDIUM, requester_resolved=null

---

**GD-E13 — Multi-commitment email**
```
Source type: email
Text: "I'll send you the report by Friday. Also, can you confirm the meeting time for next week?"
```
Expected:
- Two separate candidates OR one combined with multiple deliverables
- First: owner=sender, deliverable=report, timing=Friday
- Second: owner=recipient, deliverable=confirm meeting time, timing=next week

---

### People/Entity Extraction (for Stage 3 specifically)

**GD-E14 — Named sender with relationship**
```
Source type: email
Sender: sam@krsinsurance.com (Samantha Katchen)
Text: "I'll get you the agent roster by EOD Monday."
```
Expected Stage 3:
- owner_text=Samantha Katchen (or "I" resolved to sender)
- requester_name=Kevin (recipient)
- counterparty_name=Samantha Katchen
- user_relationship=external_professional

---

**GD-E15 — Unknown sender**
```
Source type: email
Sender: noreply@calendly.com
Text: "Your meeting with John Smith has been confirmed for Thursday at 2pm."
```
Expected:
- Stage 0: REJECT — automated/noreply sender

---

### Confidence Scoring Edge Cases

**GD-E16 — Very high confidence (should surface immediately)**
```
Source type: email
Text: "I will deliver the final report by Wednesday March 30th at 5pm EST."
```
Expected:
- confidence_commitment=0.95+
- timing_ambiguity=NONE (exact date + time)
- is_surfaced=true (high enough to surface)

---

**GD-E17 — Very low confidence (should observe, not surface)**
```
Source type: email
Text: "We should probably catch up sometime soon."
```
Expected:
- candidate_present=true (borderline)
- confidence_commitment=0.35–0.45
- lifecycle_state=observing, is_surfaced=false

---

**GD-E18 — Delivery signal (past commitment completed)**
```
Source type: email
Text: "Attached is the final report you requested."
```
Expected:
- Stage 1: trigger=delivery_signal
- Stage 3: delivery_state=delivered
- Should link to prior commitment if one exists

---

## Known Issues in Live Data (as of 2026-03-31)

| ID | Description | Affected signals | Stage |
|----|-------------|-----------------|-------|
| GD-KNOWN-001 | Fragments (4–5 chars) passing all stages and being promoted | "done", "well.", "We'll" — ~15 confirmed | Stage 0 / Stage 1 |
| GD-KNOWN-002 | 247 `obligation_marker` candidates stuck — never promoted or discarded | 247 candidates created ~March 30 | Stage 4 (routing) |
| GD-KNOWN-003 | 248 `follow_up_commitment` candidates stuck with 44 promoted, 204 stuck | No clear pattern for which promote | Stage 4 (routing) |
| GD-KNOWN-004 | 346 commitments all in 0.6–0.8 confidence, none surfaced | All 346 commitments | Surfacing logic |
| GD-KNOWN-005 | Marketing emails ("let me be direct", "I'll try") promoted as explicit_self_commitment | ~10-20 in current data | Stage 0 / Stage 1 |

---

## How to Use This Dataset

1. For each GD-Exx signal: feed the raw text through the pipeline debug endpoint (once built)
2. Compare actual stage output vs expected labels above
3. Any deviation = test failure, log as new known issue or confirm existing one
4. Confidence scores have ±0.1 tolerance — a score of 0.85 when expecting 0.95 is a WARN not a FAIL
5. Routing decisions (promote vs discard vs observe) must match exactly — no tolerance

---

## Extending the Dataset

When Slack or Meeting connectors are tested:
- Add GD-S01–GD-S10 for Slack signals (different chunking, thread context)
- Add GD-M01–GD-M10 for meeting transcripts (speaker-attributed, longer chunks)
- Same labeling format, add `speaker` field for meetings
