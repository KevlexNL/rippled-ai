# WO-RIPPLED-VOICE-INTERFACE

**Status:** PENDING
**Priority:** High
**Owner:** Trinity
**Created:** 2026-03-27
**Scope:** Rippled codebase — voice-first interaction layer

---

## Objective

Enable Rippled to accept audio input and produce audio output, allowing Kevin (and future users) to interact with their commitments conversationally — via voice queries, spoken reviews, and verbal updates — without requiring a screen.

---

## Context

Kevin's primary daily interface is Telegram. He already sends voice notes to Mero. The goal is to bring this same voice-native experience into Rippled itself, so the app can:
- Receive a spoken question ("What am I supposed to deliver to Matt this week?")
- Process it through the commitment detection/query layer
- Reply with a natural spoken answer

This does NOT mean building a phone app. The initial target is a voice-capable API endpoint that OpenClaw can route Telegram voice notes through.

---

## Research Phase (Required First)

Before implementation, Trinity must:

1. **Review existing Rippled API endpoints** — understand current request/response patterns
2. **Evaluate audio processing libraries** — `openai-whisper` (local), `openai/whisper-1` (API), or `google/gemini-3.1-flash-live-preview` for STT
3. **Evaluate TTS options** — `openai/tts-1`, `google/tts`, `elevenlabs` — assess quality, latency, and cost
4. **Assess Gemini Live API feasibility** — can `gemini-3.1-flash-live-preview` replace both STT + LLM + TTS in a single call? What's the integration path?
5. **Document findings** in `ops/research/voice-interface-options.md` before writing any code

---

## Phases

### Phase 1 — STT Endpoint
- Add `POST /voice/query` endpoint accepting an audio file (m4a, mp3, wav)
- Transcribe using `openai/whisper-1` (API) as default
- Return JSON: `{ "transcript": "...", "intent": "..." }`
- Detect basic intent: `query_commitments`, `update_status`, `review_surfaced`, `unknown`

### Phase 2 — Commitment Query via Voice
- Route `query_commitments` intent to existing commitment query logic
- Support natural language queries:
  - "What did I promise Matt this week?"
  - "What's overdue?"
  - "What should I be working on today?"
- Return structured JSON response + human-readable text summary

### Phase 3 — TTS Response
- Add TTS layer to convert text summary into audio
- Default: `openai/tts-1` (voice: `nova` or `onyx`)
- `POST /voice/query` returns both JSON + audio file (base64 or URL)
- Audio should be concise — max 3 commitments per spoken response, then offer "want more?"

### Phase 4 — Gemini Live Evaluation (if feasible)
- If research confirms `gemini-3.1-flash-live-preview` supports bidirectional audio streaming:
  - Prototype a streaming voice endpoint using Gemini Live API
  - Compare latency, quality, cost vs. Whisper + Claude + TTS pipeline
  - Document recommendation in `ops/research/voice-interface-options.md`

---

## Success Criteria

- [ ] `POST /voice/query` accepts audio and returns a spoken answer
- [ ] Correctly interprets at least 3 natural query patterns (overdue, this week, by counterparty)
- [ ] Audio response is < 30 seconds for a standard 3-commitment summary
- [ ] Latency from upload to audio response < 8 seconds
- [ ] No hard dependencies on paid libs not already in the stack
- [ ] Gemini Live feasibility documented (even if not implemented)

---

## Out of Scope

- Mobile app or native voice UI
- Real-time streaming (Phase 4 is an evaluation, not a requirement)
- Multi-user voice profiles (single user: Kevin)

---

## Files to Create/Modify

- `app/routers/voice.py` — new router
- `app/services/voice/stt_service.py` — STT abstraction
- `app/services/voice/tts_service.py` — TTS abstraction
- `app/services/voice/intent_parser.py` — basic intent detection
- `ops/research/voice-interface-options.md` — research output (before coding)

---

## Dependencies

- `WO-RIPPLED-LLM-ORCHESTRATION` (completed) — query layer must be stable
- OpenAI API key must be configured in env (`OPENAI_API_KEY`)

---

## Notify When Done

Mero + Kevin via Rippled Telegram group
