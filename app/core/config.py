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

    # OpenAI (detection pipeline)
    openai_api_key: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
