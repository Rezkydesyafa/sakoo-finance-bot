import os
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any

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
from app.models import BotLog, Job, Receipt
from app.modules.jobs.service import get_receipt_ocr_enqueue
from app.modules.ocr.client import OcrClientError, OcrResult
from app.workers.tasks import run_receipt_ocr_job


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
) -> Iterator[
    tuple[
        TestClient,
        sessionmaker[Session],
        FakeOcrClient,
        list[dict[str, Any]],
    ]
]:
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.setenv("MEDIA_RECEIPT_MAX_BYTES", "5242880")
    monkeypatch.setenv("OCR_DAILY_LIMIT_PER_USER", "20")
    monkeypatch.setenv("OCR_RATE_LIMIT_TIMEZONE", "Asia/Jakarta")
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
    queued_jobs: list[dict[str, Any]] = []

    def override_get_db() -> Iterator[Session]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def fake_enqueue(**kwargs: Any) -> None:
        queued_jobs.append(kwargs)

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_receipt_ocr_enqueue] = lambda: fake_enqueue

    with TestClient(app) as client:
        yield client, TestingSessionLocal, fake_ocr_client, queued_jobs

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    get_settings.cache_clear()


def test_receipt_ocr_endpoint_queues_background_job(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeOcrClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_ocr, queued_jobs = test_client
    token = _register_and_login(client, "owner@example.com")
    media_id = _upload_receipt(client, token)

    response = client.post(
        f"/api/ocr/receipts/{media_id}",
        headers=_auth_headers(token),
    )

    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["job"]["status"] == "queued"
    assert payload["job"]["job_type"] == "receipt_ocr"
    assert payload["message"] == "Receipt OCR job queued"
    assert queued_jobs == [
        {
            "job_id": payload["job"]["id"],
            "user_id": payload["job"]["user_id"],
            "media_id": media_id,
            "source": "dashboard",
            "notify_chat_id": None,
            "notify_session": None,
            "notify_platform": None,
        }
    ]
    assert fake_ocr.calls == 0
    job_response = client.get(
        f"/api/jobs/{payload['job']['id']}",
        headers=_auth_headers(token),
    )
    assert job_response.status_code == 200
    assert job_response.json()["status"] == "queued"

    with session_factory() as db:
        job = db.get(Job, payload["job"]["id"])
        assert job is not None
        assert job.status == "queued"
        assert job.result_id is None
        assert db.scalar(select(Receipt)) is None
        logs = db.scalars(select(BotLog).order_by(BotLog.id)).all()
        assert [log.status for log in logs] == ["ocr_usage"]
        assert logs[0].parsed_result["job_id"] == job.id


def test_receipt_ocr_worker_saves_raw_text_and_completes_job(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeOcrClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_ocr, queued_jobs = test_client
    token = _register_and_login(client, "owner@example.com")
    media_id = _upload_receipt(client, token)
    queue_response = client.post(
        f"/api/ocr/receipts/{media_id}",
        headers=_auth_headers(token),
    )
    job_id = int(queue_response.json()["job"]["id"])
    user_id = int(queue_response.json()["job"]["user_id"])

    with session_factory() as db:
        result = run_receipt_ocr_job(
            db,
            job_id=job_id,
            user_id=user_id,
            media_id=media_id,
            source="dashboard",
            ocr_client=fake_ocr,
        )

    assert result == {"status": "completed", "job_id": job_id, "receipt_id": 1}
    assert queued_jobs[0]["job_id"] == job_id
    assert fake_ocr.calls == 1

    with session_factory() as db:
        receipt = db.scalar(select(Receipt).where(Receipt.media_file_id == media_id))
        job = db.get(Job, job_id)
        assert receipt is not None
        assert receipt.ocr_text == fake_ocr.text
        assert receipt.merchant_name == "TOKO SAKOO"
        assert str(receipt.total_amount) == "20000.00"
        assert receipt.status == "processed"
        assert job is not None
        assert job.status == "completed"
        assert job.result_id == receipt.id
        assert job.completed_at is not None


def test_receipt_ocr_is_isolated_by_current_user(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeOcrClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, _session_factory, fake_ocr, queued_jobs = test_client
    token_a = _register_and_login(client, "user-a@example.com")
    token_b = _register_and_login(client, "user-b@example.com")
    media_id = _upload_receipt(client, token_a)

    response = client.post(
        f"/api/ocr/receipts/{media_id}",
        headers=_auth_headers(token_b),
    )

    assert response.status_code == 404
    assert fake_ocr.calls == 0
    assert queued_jobs == []


def test_receipt_ocr_worker_marks_job_failed_on_google_api_error(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeOcrClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_ocr, _queued_jobs = test_client
    token = _register_and_login(client, "owner@example.com")
    media_id = _upload_receipt(client, token)
    queue_response = client.post(
        f"/api/ocr/receipts/{media_id}",
        headers=_auth_headers(token),
    )
    job_id = int(queue_response.json()["job"]["id"])
    user_id = int(queue_response.json()["job"]["user_id"])
    fake_ocr.error = OcrClientError(
        "Google Vision quota exceeded",
        status_code=503,
    )

    with pytest.raises(OcrClientError):
        with session_factory() as db:
            run_receipt_ocr_job(
                db,
                job_id=job_id,
                user_id=user_id,
                media_id=media_id,
                source="dashboard",
                ocr_client=fake_ocr,
            )

    with session_factory() as db:
        receipt = db.scalar(select(Receipt).where(Receipt.media_file_id == media_id))
        job = db.get(Job, job_id)
        assert receipt is not None
        assert receipt.ocr_text is None
        assert receipt.status == "error"
        assert job is not None
        assert job.status == "failed"
        assert job.error_message == "Google Vision quota exceeded"


def test_receipt_ocr_queue_enforces_daily_limit(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeOcrClient,
        list[dict[str, Any]],
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session_factory, fake_ocr, queued_jobs = test_client
    monkeypatch.setenv("OCR_DAILY_LIMIT_PER_USER", "1")
    get_settings.cache_clear()
    token = _register_and_login(client, "owner@example.com")
    first_media_id = _upload_receipt(client, token)
    second_media_id = _upload_receipt(client, token)

    first_response = client.post(
        f"/api/ocr/receipts/{first_media_id}",
        headers=_auth_headers(token),
    )
    second_response = client.post(
        f"/api/ocr/receipts/{second_media_id}",
        headers=_auth_headers(token),
    )

    assert first_response.status_code == 202, first_response.text
    assert second_response.status_code == 429
    assert "Batas OCR harian tercapai" in second_response.json()["detail"]
    assert fake_ocr.calls == 0
    assert len(queued_jobs) == 1

    with session_factory() as db:
        logs = db.scalars(select(BotLog).order_by(BotLog.id)).all()
        assert [log.status for log in logs] == ["ocr_usage", "ocr_limit_reached"]
        assert logs[0].platform == "dashboard"
        assert logs[0].parsed_result["used_after"] == 1
        assert logs[1].parsed_result["rate_limit"]["limit"] == 1


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
