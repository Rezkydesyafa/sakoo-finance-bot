import os
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-jwt-secret-minimum-32-characters"

from app.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import Receipt
from app.modules.ocr.client import OcrClientError, OcrResult, get_ocr_client


class FakeOcrClient:
    def __init__(self) -> None:
        self.text = "TOKO SAKOO\nTOTAL 20.000"
        self.error: OcrClientError | None = None
        self.calls = 0

    def extract_text(self, image_content: bytes) -> OcrResult:
        self.calls += 1
        if self.error:
            raise self.error
        assert image_content
        return OcrResult(text=self.text)


@pytest.fixture()
def test_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session], FakeOcrClient]]:
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.setenv("MEDIA_RECEIPT_MAX_BYTES", "5242880")
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
    fake_ocr_client = FakeOcrClient()

    def override_get_db() -> Iterator[Session]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_ocr_client] = lambda: fake_ocr_client

    with TestClient(app) as client:
        yield client, TestingSessionLocal, fake_ocr_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    get_settings.cache_clear()


def test_receipt_ocr_saves_raw_text(
    test_client: tuple[TestClient, sessionmaker[Session], FakeOcrClient],
) -> None:
    client, session_factory, fake_ocr = test_client
    token = _register_and_login(client, "owner@example.com")
    media_id = _upload_receipt(client, token)

    response = client.post(
        f"/api/ocr/receipts/{media_id}",
        headers=_auth_headers(token),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["media_file_id"] == media_id
    assert payload["ocr_text"] == fake_ocr.text
    assert payload["merchant_name"] == "TOKO SAKOO"
    assert payload["total_amount"] == "20000.00"
    assert Decimal(payload["confidence"]) >= Decimal("0.7500")
    assert payload["status"] == "processed"
    assert fake_ocr.calls == 1

    with session_factory() as db:
        receipt = db.scalar(select(Receipt).where(Receipt.media_file_id == media_id))
        assert receipt is not None
        assert receipt.ocr_text == fake_ocr.text
        assert receipt.merchant_name == "TOKO SAKOO"
        assert str(receipt.total_amount) == "20000.00"
        assert receipt.status == "processed"


def test_receipt_ocr_is_isolated_by_current_user(
    test_client: tuple[TestClient, sessionmaker[Session], FakeOcrClient],
) -> None:
    client, _session_factory, fake_ocr = test_client
    token_a = _register_and_login(client, "user-a@example.com")
    token_b = _register_and_login(client, "user-b@example.com")
    media_id = _upload_receipt(client, token_a)

    response = client.post(
        f"/api/ocr/receipts/{media_id}",
        headers=_auth_headers(token_b),
    )

    assert response.status_code == 404
    assert fake_ocr.calls == 0


def test_receipt_ocr_handles_google_api_error(
    test_client: tuple[TestClient, sessionmaker[Session], FakeOcrClient],
) -> None:
    client, session_factory, fake_ocr = test_client
    token = _register_and_login(client, "owner@example.com")
    media_id = _upload_receipt(client, token)
    fake_ocr.error = OcrClientError(
        "Google Vision quota exceeded",
        status_code=503,
    )

    response = client.post(
        f"/api/ocr/receipts/{media_id}",
        headers=_auth_headers(token),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Google Vision quota exceeded"

    with session_factory() as db:
        receipt = db.scalar(select(Receipt).where(Receipt.media_file_id == media_id))
        assert receipt is not None
        assert receipt.ocr_text is None
        assert receipt.status == "error"


def _upload_receipt(client: TestClient, token: str) -> int:
    response = client.post(
        "/api/media",
        headers=_auth_headers(token),
        data={"file_type": "receipt", "source": "dashboard_upload"},
        files={"file": ("receipt.jpg", b"fake-jpeg-content", "image/jpeg")},
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _register_and_login(client: TestClient, email: str) -> str:
    password = "super-secret-password"
    register_response = client.post(
        "/api/auth/register",
        json={
            "name": email.split("@", 1)[0],
            "email": email,
            "password": password,
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    return login_response.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
