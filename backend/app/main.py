from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import router as api_router
from app.config import get_settings
from app.database import check_database_connection
from app.modules.auth.router import router as auth_router
from app.modules.transactions.router import router as transactions_router
from app.modules.waha.router import router as waha_router


settings = get_settings()


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
    app.include_router(auth_router, prefix=settings.api_prefix)
    app.include_router(transactions_router, prefix=settings.api_prefix)
    app.include_router(waha_router)

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
