from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Sakoo Finance Bot"
    app_env: str = "local"
    api_prefix: str = "/api"
    debug: bool = False

    database_url: str = Field(..., description="PostgreSQL connection URL")
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    frontend_origin: str = "http://localhost:3001"
    app_base_url: str = "https://sakoo.lab-sigma.web.id"
    storage_path: str = "storage"
    media_receipt_max_bytes: int = 5 * 1024 * 1024
    media_default_max_bytes: int = 10 * 1024 * 1024

    jwt_secret: str = ""
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    account_linking_code_ttl_minutes: int = 10

    telegram_bot_token: str = ""
    telegram_base_url: str = "https://api.telegram.org"
    telegram_timeout_seconds: float = 10.0
    telegram_webhook_secret: str = ""
    telegram_register_commands_on_startup: bool = False
    telegram_dashboard_url: str = "https://sakoo.lab-sigma.web.id"
    waha_base_url: str = "http://localhost:3002"
    waha_api_key: str = ""
    waha_session_name: str = "default"
    waha_timeout_seconds: float = 10.0
    waha_webhook_hmac_key: str = ""
    google_application_credentials: str = ""
    ocr_daily_limit_per_user: int = 20
    ocr_rate_limit_timezone: str = "Asia/Jakarta"
    stt_language_code: str = "id-ID"
    stt_max_duration_seconds: int = 30
    stt_enable_automatic_punctuation: bool = True
    llm_provider: str = "none"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen2.5:1.5b"
    ollama_timeout_seconds: float = 30.0
    gemini_api_key: str = ""
    gemini_api_key_1: str = ""
    gemini_api_key_2: str = ""
    gemini_api_keys: str = ""
    gemini_model: str = "gemini-1.5-flash"
    glm_api_key: str = ""
    glm_model: str = "glm-4-flash"
    openrouter_api_key: str = ""
    openrouter_model: str = "deepseek/deepseek-chat"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    llm_timeout_seconds: float = 15.0
    llm_max_request_per_user_per_day: int = 20
    bot_reply_style: str = "friendly"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def resolved_celery_broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def resolved_celery_result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
