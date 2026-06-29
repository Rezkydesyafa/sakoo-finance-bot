import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as api_router
from app.api.webhooks import router as webhook_router
from app.core.config import get_settings
from app.core.database import check_database_connection
from app.modules.telegram.client import TelegramClientError
from app.modules.telegram.commands import register_bot_commands


settings = get_settings()
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, debug=settings.debug)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(webhook_router)

    if settings.telegram_register_commands_on_startup:

        @app.on_event("startup")
        def register_telegram_command_menu() -> None:
            try:
                register_bot_commands()
            except TelegramClientError as exc:
                logger.warning("Failed to register Telegram bot commands: %s", exc)

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

    return app


app = create_app()
