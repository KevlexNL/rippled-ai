# Voice Bridge — Twilio <-> Gemini Live

Real-time audio bridge service connecting Twilio phone calls to Google's Gemini Live API for bidirectional voice interaction.

## Architecture

```
Phone Call → Twilio → POST /twilio/voice (TwiML)
                   → WS /twilio/media-stream (audio chunks)
                        → AudioPipe
                            → GeminiLiveClient (WebSocket)
                                → Gemini Live API (STT + LLM + TTS)
                            ← GeminiResponse (text / audio / function calls)
                        ← Audio back to Twilio caller
```

## Files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app entry point |
| `twilio_handler.py` | Twilio webhook + media stream WebSocket |
| `gemini_client.py` | Gemini Live API WebSocket client |
| `audio_pipe.py` | Bidirectional audio pipe connecting Twilio to Gemini |

## Credential Configuration

The following environment variables must be set before the bridge can connect to live services.

### Twilio

| Variable | Description | Example |
|----------|-------------|---------|
| `TWILIO_ACCOUNT_SID` | Twilio Account SID | `AC1234567890abcdef...` |
| `TWILIO_AUTH_TOKEN` | Twilio Auth Token | `your_auth_token_here` |
| `TWILIO_PHONE_NUMBER` | Provisioned Twilio phone number | `+15551234567` |

**Setup steps:**
1. Create a Twilio account at https://www.twilio.com
2. Purchase a phone number with Voice capability
3. Set the Voice webhook URL to `https://<your-domain>/twilio/voice` (HTTP POST)
4. Add the credentials above to `.env`

### Google Vertex AI (Gemini Live)

| Variable | Description | Example |
|----------|-------------|---------|
| `GOOGLE_VERTEX_AI_PROJECT_ID` | Google Cloud project ID | `my-project-123` |
| `GOOGLE_VERTEX_AI_LOCATION` | Vertex AI region (default: `us-central1`) | `us-central1` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON key file | `/path/to/service-account.json` |

**Setup steps:**
1. Create a Google Cloud project
2. Enable the Vertex AI API
3. Create a service account with the `roles/aiplatform.user` role
4. Download the JSON key file
5. Set `GOOGLE_APPLICATION_CREDENTIALS` to the key file path
6. Set `GOOGLE_VERTEX_AI_PROJECT_ID` to the project ID

### OpenClaw / `.env` Integration

All credentials should be added to the project `.env` file:

```env
# Twilio Voice Bridge
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token_here
TWILIO_PHONE_NUMBER=+15551234567

# Google Vertex AI (Gemini Live)
GOOGLE_VERTEX_AI_PROJECT_ID=your-project-id
GOOGLE_VERTEX_AI_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

The FastAPI app loads these via `app.voice_bridge.config.VoiceBridgeSettings` (Pydantic Settings), which reads from environment variables or `.env`.

## Running Locally

```bash
# Start the voice bridge (standalone)
uvicorn app.voice_bridge.main:voice_app --reload --port 8001

# Or as part of the main Rippled app (once wired in)
uvicorn app.main:app --reload
```

For local testing with Twilio, use ngrok to expose your local server:

```bash
ngrok http 8001
# Then set the Twilio webhook URL to the ngrok HTTPS URL
```

## Current Status

- **Mock mode:** All Gemini Live connections use placeholder credentials. The bridge accepts Twilio webhooks and logs audio chunks, but does not forward to a real Gemini endpoint.
- **Next step:** Kevin provisions Twilio + Google Cloud accounts, Keymaker wires credentials into `.env`.
