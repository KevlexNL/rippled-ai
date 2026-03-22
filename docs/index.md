# Rippled.ai

**Commitment intelligence for small business operators.**

Rippled watches your email, Slack, and meetings and surfaces the commitments you made — and the ones made to you — before they fall through the cracks.

---

## What Is This?

This is the living product documentation for Rippled. It covers:

- **Architecture** — how the system works end to end
- **Product** — what we're building and why
- **Prompts** — the exact LLM instructions in use, versioned
- **Decisions** — why we made the choices we made
- **Work Orders** — what Trinity is working on now and what's queued

---

## Current Status

| Area | Status |
|------|--------|
| Email detection | ✅ Live |
| Slack detection | ✅ Connected |
| Read.ai meetings | ✅ Connected |
| Commitment dashboard | ✅ Live |
| User identity profiles | ✅ Live |
| Completion detection | ✅ Live |
| Speech act classification | 🔄 In progress |
| NormalizedSignal contract | 📋 Queued |
| Architecture diagram tab | 📋 Queued |

---

## Quick Links

- [Signal Pipeline](architecture/signal-pipeline.md) — how a raw email becomes a commitment
- [Commitment Lifecycle](architecture/lifecycle.md) — the full state machine
- [Domain Policy](product/domain-policy.md) — the locked product decisions
- [Active Work Orders](workorders/active.md) — what Trinity is building now
- [Detection Prompt v4](prompts/detection-v4.md) — the live extraction prompt

---

## How to Contribute (From Your Phone)

1. Open [GitHub Discussions](https://github.com/KevlexNL/rippled-ai/discussions)
2. Post a comment, question, or product idea in plain language
3. Mero checks 4x/day, interprets, creates a Work Order if needed, replies

You don't need to write code or specs. Plain language is enough.
