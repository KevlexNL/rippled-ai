
Here’s a clean, execution-ready brief you can hand to Claude Code. I’ve kept it tight, structured, and implementation-focused—no fluff.

---

# 🔧 Rippled Update Brief: Email Thread Processing & Signal Layering

## 🎯 Objective

Ensure Rippled **only uses the latest authored message as the primary signal source**, while still ingesting and leveraging full thread context in a **controlled, multi-stage processing pipeline**.

This requires:

1. Updating documentation to reflect the intended architecture
2. Enforcing this behavior in the ingestion + processing pipeline

---

# 1️⃣ Documentation Updates

## Goal

Make the “latest message first” principle a **non-negotiable system rule**, not just an implementation detail.

---

## A. Add Core Principle (Global)

Add to system design / signal processing docs:

> **Primary Signal Rule**
>
> All new signal detection (e.g. commitments, tasks, updates) MUST originate exclusively from the **latest authored message** in a thread.
>
> Quoted or prior thread content may:
>
> * provide context
> * help interpret intent
> * assist with linking to prior signals
>
> But MUST NOT:
>
> * generate new signals independently
> * override the interpretation of the latest message without explicit reconciliation logic

---

## B. Define the 3-Layer Processing Model

Add a dedicated section:

### Signal Processing Layers

#### 1. Immediate Signal Detection

* Input: `latest_authored_text`
* Output: candidate signals (commitments, updates, etc.)
* Constraint:

  * No access to prior thread content for signal creation
  * Must be self-contained interpretation

---

#### 2. Contextual Interpretation

* Input:

  * `latest_authored_text`
  * `prior_context_text` OR thread summary
* Purpose:

  * Validate / refine initial interpretation
  * Link to prior signals
  * Detect updates, completions, or confirmations

---

#### 3. Consistency & Resolution

* Input:

  * Outputs from Stage 1 + Stage 2
* Purpose:

  * Resolve conflicts
  * Finalize action:

    * create
    * update
    * complete
    * cancel
    * observe

---

## C. Define Normalized Email Contract

Update or create spec for normalized signals:

```ts
NormalizedEmailSignal {
  latest_authored_text: string        // PRIMARY signal source
  prior_context_text?: string         // quoted history
  full_visible_text: string           // full raw email body
  subject?: string
  participants: {...}
  thread_id: string
  direction: 'inbound' | 'outbound'
}
```

Explicitly document:

* `latest_authored_text` → ONLY source for new signal detection
* `prior_context_text` → context only
* `full_visible_text` → storage/audit only

---

## D. Prompting Guidelines Update

Update LLM prompt specs:

* Introduce strict sections:

  * `[CURRENT MESSAGE]`
  * `[PRIOR CONTEXT]`

Add rule:

> Only extract new signals from `[CURRENT MESSAGE]`.
> `[PRIOR CONTEXT]` may only be used to interpret or link, never to originate signals.

---

## E. Add Cost Strategy Note

Document:

* Stage 2 and 3 are **conditional**, not always executed
* Default = single-pass processing using latest message only
* Context is only invoked when ambiguity exists

---

# 2️⃣ Implementation Work

## Goal

Enforce this behavior in code so it’s **structurally impossible** to regress.

---

## A. Normalize Email Input (Mandatory Step)

### Ensure all email ingestion flows produce:

* `latest_authored_text`
* `prior_context_text`
* `full_visible_text`

### Tasks:

* [ ] Audit all email ingestion entry points
* [ ] Ensure `EmailNormalizationService` (or equivalent) is always called
* [ ] Remove any direct downstream usage of raw email body for detection

---

## B. Enforce Primary Signal Source

### Critical Rule:

Detection services MUST NOT accept full thread content.

### Tasks:

* [ ] Update signal detection interface:

```ts
detectSignals({
  latest_authored_text,
  metadata
})
```

* [ ] Remove or block usage of:

  * `full_visible_text`
  * `prior_context_text`
    in Stage 1 detection

* [ ] Add guardrails:

  * Throw/log error if full thread is passed into detection layer

---

## C. Implement Multi-Stage Pipeline

### Stage 1 — Immediate Detection (Required)

* Input:

  * `latest_authored_text`
* Output:

  * candidate signals
  * confidence score

---

### Stage 2 — Contextual Interpretation (Conditional)

Trigger ONLY IF:

* confidence is below threshold
* message is ambiguous
* message references prior context (e.g. “that works”, “done”, “as discussed”)

Input:

* `latest_authored_text`
* `prior_context_text` OR thread summary

---

### Stage 3 — Consistency Resolution (Rare)

Trigger ONLY IF:

* conflict between Stage 1 and Stage 2
* high-value signal (deadline, ownership, etc.)

---

## D. Add Context Gating Logic

Implement lightweight pre-check before Stage 2:

```ts
shouldUseContext(signalCandidate) => boolean
```

Conditions:

* lacks clear action verb
* missing subject/object
* ambiguous intent

---

## E. Optional Optimization (Recommended)

### Thread Summary Cache

Instead of passing full `prior_context_text`:

* [ ] Generate thread summary after first email
* [ ] Store per `thread_id`
* [ ] Use summary in Stage 2 instead of full history

---

## F. Update Prompts

### Stage 1 Prompt

* ONLY includes:

  * `[CURRENT MESSAGE]`

---

### Stage 2 Prompt

* Includes:

  * `[CURRENT MESSAGE]`
  * `[PRIOR CONTEXT]` or `[THREAD SUMMARY]`

---

## G. Logging & Observability

Add structured logs:

* Stage 1 result
* Whether Stage 2 triggered
* Whether Stage 3 triggered
* Final resolution decision

This is critical for debugging and trust.

---

## H. Backward Compatibility / Migration

* [ ] Ensure existing stored signals remain valid
* [ ] Do not reprocess old data unless explicitly triggered
* [ ] New pipeline applies to new incoming signals only

---

# ✅ Definition of Done

* Detection layer ONLY uses `latest_authored_text`
* Context is never used to originate new signals
* Multi-stage pipeline is implemented with conditional execution
* Documentation clearly reflects architecture and constraints
* No code path exists where full email thread is used as primary signal

---

# 💬 Final Note (for Claude)

This is not just a refactor — this is a **core architectural rule**.

If there is any ambiguity:

* Prefer **strict separation**
* Prefer **explicit contracts over implicit behavior**
* Prevent future regressions through **interfaces and guardrails**, not just prompts

---

If you want next step, I can:

* Turn this into a **task list per file/module in your repo**
* Or write **actual pseudo-code / function signatures** for each stage so Claude can implement faster
