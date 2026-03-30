# Voice Interface Options — Research

**Author:** Trinity  
**Date:** 2026-03-31  
**WO:** WO-RIPPLED-VOICE-INTERFACE

---

## 1. STT Options

### OpenAI Whisper API (`openai/whisper-1`)
- **Model:** Hosted, accessed via `openai.audio.transcriptions.create`
- **Input:** m4a, mp3, wav, ogg, webm — up to 25 MB
- **Latency:** ~1–3 s for a 30-second clip
- **Cost:** $0.006/min — a 30-second clip ≈ $0.003
- **Accuracy:** Very high for English speech; handles names and technical terms well
- **Integration path:** Already have `openai` package and `OPENAI_API_KEY` in stack. Zero new dependencies.
- **Verdict:** ✅ Selected as default

### Local Whisper (`openai-whisper` PyPI)
- **Pros:** No API cost, no network hop
- **Cons:** ~1 GB model download, CPU-only on this server = slow (10–30 s for 30-second clip), adds `torch` dep
- **Verdict:** ❌ Not suitable for <8s latency target

### Google Speech-to-Text
- **Pros:** Fast, good accuracy
- **Cons:** New GCP creds, new SDK dep, more complexity
- **Verdict:** ❌ Unnecessary; Whisper API covers the use case

---

## 2. TTS Options

### OpenAI TTS (`openai/tts-1`)
- **Input:** Text up to 4096 chars
- **Output:** mp3 stream
- **Voices:** `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`
- **Latency:** ~1–2 s for a short paragraph
- **Cost:** $0.015/1K chars — a 300-char response ≈ $0.0045
- **Integration:** Same `openai` client, no new deps
- **Verdict:** ✅ Selected — voice `nova`

### ElevenLabs
- **Pros:** More natural, customizable voice
- **Cons:** New SDK, new API key, higher cost ($0.30/1K chars on starter)
- **Verdict:** ❌ Overkill for the current use case

### Google Cloud TTS
- **Pros:** Good quality, Wavenet voices
- **Cons:** New GCP dep, additional auth complexity
- **Verdict:** ❌ Unnecessary overhead

---

## 3. Gemini Live API Feasibility

### `gemini-2.5-flash-native-audio-latest` (previously flash-live-preview)
- **What it does:** Bidirectional real-time audio streaming (WebSocket-based)
- **Latency:** Designed for conversational latency; sub-second turns in ideal conditions
- **Limitations:**
  - Requires persistent WebSocket session — doesn't map cleanly to stateless HTTP `POST /voice/query`
  - Not suitable for fire-and-forget audio upload → response model
  - Already used in voice bridge (Twilio integration) for phone call handling
- **Verdict:** ⚠️ Not suitable for HTTP endpoint pattern. Best reserved for real-time call flows (already implemented in voice bridge). A future streaming upgrade could layer Gemini Live on top of the `/voice/stream` WebSocket endpoint.

---

## 4. Selected Architecture

```
POST /voice/query
   ├── Receive audio file (UploadFile: m4a, mp3, wav)
   ├── STT: openai/whisper-1 → transcript
   ├── Intent parser: LLM-based classification
   │       query_commitments | update_status | review_surfaced | unknown
   ├── Query layer: DB query based on intent + transcript
   ├── Summarizer: GPT-4.1-mini → concise spoken summary (≤3 commitments)
   └── TTS: openai/tts-1 (nova) → mp3 bytes → base64 in response
```

**Estimated end-to-end latency:** ~3–6 s  
**Estimated per-request cost:** ~$0.01–0.02 (STT + LLM + TTS)

---

## 5. Dependency Changes

- `python-multipart` — for FastAPI file upload (already installed)
- No new packages needed

---

## 6. Future Improvements

- `POST /voice/stream` WebSocket endpoint using Gemini Live for real-time conversation
- Voice profile per user (preferred TTS voice stored in user settings)
- Caching TTS responses for repeated queries ("what's overdue?" has a predictable output)
