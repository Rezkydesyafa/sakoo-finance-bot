import os
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-jwt-secret-minimum-32-characters"
os.environ["WAHA_SESSION_NAME"] = "default"

from app.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import BotLog
from app.modules.waha.client import WahaClientError, get_waha_client


class FakeWahaClient:
    def __init__(self) -> None:
        self.session = "default"
        self.payload: dict[str, Any] = {"status": "WORKING"}
        self.error: WahaClientError | None = None
        self.requested_session: str | None = None

    def get_session_status(self, session: str | None = None) -> dict[str, Any]:
        self.requested_session = session
        if self.error:
            raise self.error
        return self.payload


@pytest.fixture()
def test_client() -> Iterator[tuple[TestClient, sessionmaker[Session], FakeWahaClient]]:
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)
    fake_waha_client = FakeWahaClient()

    def override_get_db() -> Iterator[Session]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_waha_client] = lambda: fake_waha_client

    with TestClient(app) as client:
        yield client, TestingSessionLocal, fake_waha_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    get_settings.cache_clear()


def test_waha_health_returns_ok_when_session_working(
    test_client: tuple[TestClient, sessionmaker[Session], FakeWahaClient],
) -> None:
    client, session_factory, fake_waha = test_client
    fake_waha.payload = {"status": "WORKING", "name": "default"}

    response = client.get("/health/waha")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["healthy"] is True
    assert payload["session"] == "default"
    assert payload["session_status"] == "WORKING"
    assert payload["warning"] is None
    assert fake_waha.requested_session == "default"

    with session_factory() as db:
        assert db.scalar(select(BotLog)) is None


def test_waha_health_returns_503_and_logs_when_session_not_working(
    test_client: tuple[TestClient, sessionmaker[Session], FakeWahaClient],
) -> None:
    client, session_factory, fake_waha = test_client
    fake_waha.payload = {"status": "STOPPED", "name": "default"}

    response = client.get("/health/waha")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["status"] == "error"
    assert detail["healthy"] is False
    assert detail["session_status"] == "STOPPED"
    assert "WAHA session is not active" in detail["warning"]

    with session_factory() as db:
        log = db.scalar(select(BotLog))
        assert log is not None
        assert log.platform == "system"
        assert log.message_type == "waha_health"
        assert log.status == "waha_unhealthy"
        assert "STOPPED" in (log.error_message or "")


def test_waha_health_returns_503_and_logs_when_waha_request_fails(
    test_client: tuple[TestClient, sessionmaker[Session], FakeWahaClient],
) -> None:
    client, session_factory, fake_waha = test_client
    fake_waha.error = WahaClientError(
        "WAHA returned HTTP 503.",
        status_code=503,
        response_body="service unavailable",
    )

    response = client.get("/health/waha")

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["status"] == "error"
    assert detail["healthy"] is False
    assert detail["session_status"] is None
    assert "WAHA health check failed" in detail["warning"]
    assert detail["raw"]["status_code"] == 503

    with session_factory() as db:
        log = db.scalar(select(BotLog))
        assert log is not None
        assert log.platform == "system"
        assert log.message_type == "waha_health"
        assert log.status == "waha_unhealthy"
        assert "WAHA health check failed" in (log.error_message or "")
