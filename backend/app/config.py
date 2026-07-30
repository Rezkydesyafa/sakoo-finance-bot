import re
from functools import lru_cache
from typing import Self

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


CUSTOM_PROVIDER_NAME_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")
LLM_PROVIDER_SPLIT_RE = re.compile(r"[\s,;|+>]+")


class CustomLlmProviderSettings(BaseModel):
    base_url: AnyHttpUrl
    api_key: str
    model: str

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.query or value.fragment:
            raise ValueError("must not contain a query string or fragment")
        if value.path.rstrip("/").endswith("/chat/completions"):
            raise ValueError("must be a base URL, not a chat completions endpoint")
        return value

    @field_validator("api_key", "model", mode="before")
    @classmethod
    def validate_required_text(cls, value: object) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("must not be empty")
        return normalized


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
    google_oauth_client_id: str = ""
    google_oauth_client_secret: str = ""
    google_oauth_redirect_uri: str = ""
    ocr_daily_limit_per_user: int = 20
    ocr_rate_limit_timezone: str = "Asia/Jakarta"
    stt_language_code: str = "id-ID"
    stt_max_duration_seconds: int = 30
    stt_enable_automatic_punctuation: bool = True
    llm_provider: str = Field(..., description="Comma-separated LLM provider fallback order")
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = Field(..., description="Ollama fallback model name")
    ollama_timeout_seconds: float = 30.0
    gemini_api_key: str = ""
    gemini_api_key_1: str = ""
    gemini_api_key_2: str = ""
    gemini_api_keys: str = ""
    gemini_model: str = Field(..., description="Gemini model name")
    glm_api_key: str = ""
    glm_model: str = Field(..., description="GLM model name")
    openrouter_api_key: str = ""
    openrouter_model: str = Field(..., description="OpenRouter fallback model name")
    deepseek_api_key: str = ""
    deepseek_model: str = Field(..., description="DeepSeek model name")
    custom_llm_providers: dict[str, CustomLlmProviderSettings] = Field(
        default_factory=dict,
        description="Named OpenAI-compatible LLM providers",
    )
    llm_timeout_seconds: float = 15.0
    llm_max_request_per_user_per_day: int = 20
    bot_reply_style: str = "friendly"

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_custom_llm_provider_references(self) -> Self:
        for name in self.custom_llm_providers:
            if not CUSTOM_PROVIDER_NAME_RE.fullmatch(name):
                raise ValueError(
                    f"invalid custom LLM provider name: {name!r}; "
                    "use lowercase letters, numbers, '_' or '-'"
                )

        provider_names = [
            item
            for item in LLM_PROVIDER_SPLIT_RE.split(self.llm_provider.strip().lower())
            if item
        ]
        for provider_name in provider_names:
            if provider_name == "custom":
                raise ValueError("custom LLM provider must use custom:<name>")
            if not provider_name.startswith("custom:"):
                continue
            custom_name = provider_name.removeprefix("custom:")
            if (
                not CUSTOM_PROVIDER_NAME_RE.fullmatch(custom_name)
                or custom_name not in self.custom_llm_providers
            ):
                raise ValueError(
                    f"custom LLM provider {provider_name!r} is not configured"
                )
        return self

    @property
    def resolved_celery_broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def resolved_celery_result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url


@lru_cache
def get_settings() -> Settings:
    return Settings()
