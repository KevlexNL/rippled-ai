"""Voice bridge configuration.

Loads Twilio and Google Vertex AI credentials from environment variables.
All fields default to empty/placeholder — the bridge runs in mock mode
until real credentials are provided.
"""
from pydantic_settings import BaseSettings


class VoiceBridgeSettings(BaseSettings):
    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # Google Vertex AI (Gemini Live)
    google_vertex_ai_project_id: str = "PLACEHOLDER_PROJECT_ID"
    google_vertex_ai_location: str = "us-central1"
    google_application_credentials: str = ""

    # Gemini model
    gemini_live_model: str = "gemini-2.5-flash-native-audio"

    class Config:
        env_file = ".env"
        case_sensitive = False
