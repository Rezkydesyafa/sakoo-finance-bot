from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Sakoo Finance Bot"
    app_env: str = "local"
    debug: bool = False

    database_url: str = Field(
        default="postgresql+psycopg://sakoo:sakoo@localhost:5432/sakoo_finance"
    )
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None

    frontend_origin: str = "http://localhost:3001"
    app_base_url: str = "http://localhost"
    storage_path: str = "storage"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    telegram_bot_token: str = ""
    waha_base_url: str = "http://localhost:3000"
    waha_api_key: str = ""
    google_application_credentials: str = ""

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
