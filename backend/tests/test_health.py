import asyncio
import os

import httpx

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://localhost/sakoo_finance")

from app.main import app


async def request(path: str) -> httpx.Response:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        return await client.get(path)


def get(path: str) -> httpx.Response:
    return asyncio.run(request(path))


def test_health_check() -> None:
    response = get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_router_prefix() -> None:
    response = get("/api/")

    assert response.status_code == 200
    assert response.json() == {"message": "Sakoo Finance Bot API"}


def test_swagger_docs_available() -> None:
    response = get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text
