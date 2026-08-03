import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as api_router
from app.api.webhooks import router as webhook_router
from app.config import get_settings
from app.database import check_database_connection
from app.modules.telegram.client import TelegramClientError
from app.modules.telegram.commands import register_bot_commands

settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if settings.telegram_register_commands_on_startup:
        try:
            register_bot_commands()
        except TelegramClientError as exc:
            logger.warning("Failed to register Telegram bot commands: %s", exc)
    yield


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in str(settings.frontend_origin).split(",")],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(webhook_router)

    @app.get("/")
    def read_root() -> dict[str, str]:
        return {"message": "Sakoo Finance Bot API"}

    @app.get("/health", tags=["health"])
    def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/db", tags=["health"])
    def database_health_check() -> dict[str, str]:
        check_database_connection()
        return {"status": "ok"}

    @app.get("/health/ollama", tags=["health"])
    def ollama_health_check() -> dict[str, object]:
        from app.modules.llm.base import LlmProviderConfig
        from app.modules.llm.ollama_provider import OllamaProvider

        provider = OllamaProvider(
            LlmProviderConfig(
                api_key="",
                timeout_seconds=settings.ollama_timeout_seconds,
                model=settings.ollama_model,
            ),
            base_url=settings.ollama_base_url,
        )
        server_ok = provider.is_available()
        model_ok = provider.has_model() if server_ok else False
        status = "ok" if server_ok and model_ok else "degraded" if server_ok else "unavailable"
        return {
            "status": status,
            "server_reachable": server_ok,
            "model": settings.ollama_model,
            "model_available": model_ok,
            "base_url": settings.ollama_base_url,
        }

    return app


app = create_app()
