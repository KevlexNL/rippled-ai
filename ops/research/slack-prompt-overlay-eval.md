# Slack Prompt Overlay Evaluation

**Status:** Pending live data eval after DB reseed
**Overlay version:** slack_overlay_v1
**Date:** 2026-03-29

---

## Overview

Formal evaluation requires live Slack signals in the database. This document describes the 5 key patterns the overlay addresses and the evaluation plan once data is available.

---

## Key Patterns Addressed

### 1. Terse Acceptance in Thread Replies
**Pattern:** User replies "will do" / "on it" / "yep" to a thread containing a task request.
**Without overlay:** Classified as `information` or `unclear` — no commitment detected.
**With overlay:** Classified as `acceptance` or `self_commitment` with thread parent providing deliverable context.

### 2. Emoji-as-Reply Acceptance
**Pattern:** User replies with 👍 or ✅ to a direct request.
**Without overlay:** Ignored entirely — emoji-only messages have no text for the model to analyze.
**With overlay:** Treated as likely acceptance with low-to-medium confidence, pending thread context.

### 3. Request vs. Commitment Confusion
**Pattern:** "lmk", "can you check this?", "let me know" misclassified as commitments.
**Without overlay:** Model sometimes interprets requests as self-commitments (false positive).
**With overlay:** Explicit false-positive guard prevents promotion of request language.

### 4. Social Acknowledgement Noise
**Pattern:** "sounds good", "nice", "👏" treated as acceptance.
**Without overlay:** Model may classify casual social responses as commitment signals.
**With overlay:** Guard rules explicitly exclude social-only responses.

### 5. Channel Context for Ownership
**Pattern:** DM vs. public channel @mention changes ownership confidence.
**Without overlay:** All Slack messages treated identically regardless of channel type.
**With overlay:** DM signals get higher ownership confidence; @mention in public channels flagged as potential delegation.

---

## Evaluation Plan

Once Slack signals are available in the database:

1. Sample 20 Slack `NormalizedSignal` objects spanning all 5 patterns above
2. Run each through the pipeline **without** overlay (baseline)
3. Run each through the pipeline **with** overlay
4. Compare:
   - False positive rate (non-commitments classified as commitments)
   - False negative rate (commitments missed)
   - Confidence score changes
   - Speech act classification accuracy
5. Document results in this file with before/after comparison table
