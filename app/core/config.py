from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    database_url: str

    # App
    app_env: str = "development"
    secret_key: str
    api_prefix: str = "/api/v1"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # OpenAI (model detection pipeline)
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    model_detection_enabled: bool = True

    # Email connector (IMAP)
    imap_host: str = ""
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_ssl: bool = True
    imap_sent_folder: str = "Sent"
    email_webhook_secret: str = ""
    internal_domains: str = ""  # comma-separated list

    # Slack connector
    slack_signing_secret: str = ""
    slack_bot_token: str = ""
    slack_team_id: str = ""
    slack_user_id: str = ""  # the Rippled user's Slack user ID

    # Meeting connector
    meeting_webhook_secret: str = ""

    # Credential encryption
    encryption_key: str = ""

    # Public base URL for webhook URL generation (e.g. https://api.rippled.ai)
    base_url: str = ""

    # Google Calendar integration
    google_calendar_enabled: bool = False
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = ""
    google_calendar_user_email: str = ""  # defaults to digest_to_email if empty

    # Counterparty classification
    internal_managers: str = ""  # comma-separated email list for internal_manager detection

    # Daily digest / email delivery
    digest_enabled: bool = True
    digest_smtp_host: str = ""
    digest_smtp_port: int = 587
    digest_smtp_user: str = ""
    digest_smtp_pass: str = ""
    digest_from_email: str = "digest@rippled.ai"
    digest_to_email: str = ""
    sendgrid_api_key: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
