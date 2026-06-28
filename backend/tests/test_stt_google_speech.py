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
from app.models import Category, Job, Transaction, VoiceNote
from app.modules.jobs.service import get_voice_stt_enqueue
from app.modules.stt.client import SttClientError, SttResult
from app.workers.tasks import run_voice_stt_job


class FakeSttClient:
    def __init__(self) -> None:
        self.text = "beli makan dua puluh ribu"
        self.error: SttClientError | None = None
        self.calls = 0

    def transcribe(
        self,
        audio_content: bytes,
        *,
        mime_type: str | None = None,
        sample_rate_hertz: int | None = None,
    ) -> SttResult:
        self.calls += 1
        if self.error:
            raise self.error
        assert audio_content
        assert mime_type == "audio/ogg"
        assert sample_rate_hertz == 48_000
        return SttResult(text=self.text)


@pytest.fixture()
def test_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[
    tuple[
        TestClient,
        sessionmaker[Session],
        FakeSttClient,
        list[dict[str, Any]],
    ]
]:
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "storage"))
    monkeypatch.setenv("STT_MAX_DURATION_SECONDS", "30")
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

    with TestingSessionLocal() as db:
        db.add_all(
            [
                Category(name="Makanan", type="expense"),
                Category(name="Lainnya", type="expense"),
            ]
        )
        db.commit()

    fake_stt_client = FakeSttClient()
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
    app.dependency_overrides[get_voice_stt_enqueue] = lambda: fake_enqueue

    with TestClient(app) as client:
        yield client, TestingSessionLocal, fake_stt_client, queued_jobs

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    get_settings.cache_clear()


def test_voice_stt_endpoint_queues_background_job(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeSttClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, _session_factory, fake_stt, queued_jobs = test_client
    token = _register_and_login(client, "owner@example.com")
    media_id = _upload_audio(client, token, duration_seconds=10)

    response = client.post(
        f"/api/stt/transcribe/{media_id}",
        headers=_auth_headers(token),
    )

    assert response.status_code == 202, response.text
    payload = response.json()
    assert payload["job"]["status"] == "queued"
    assert payload["job"]["job_type"] == "voice_stt"
    assert payload["message"] == "Voice STT job queued"
    assert queued_jobs == [
        {
            "job_id": payload["job"]["id"],
            "user_id": payload["job"]["user_id"],
            "media_id": media_id,
            "source": "dashboard",
            "duration_seconds": None,
            "notify_chat_id": None,
            "notify_session": None,
            "notify_platform": None,
        }
    ]
    assert fake_stt.calls == 0


def test_voice_stt_worker_saves_transcript_and_transaction(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeSttClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_stt, _queued_jobs = test_client
    token = _register_and_login(client, "owner@example.com")
    media_id = _upload_audio(client, token, duration_seconds=10)
    queue_response = client.post(
        f"/api/stt/transcribe/{media_id}",
        headers=_auth_headers(token),
    )
    job_id = int(queue_response.json()["job"]["id"])
    user_id = int(queue_response.json()["job"]["user_id"])

    with session_factory() as db:
        result = run_voice_stt_job(
            db,
            job_id=job_id,
            user_id=user_id,
            media_id=media_id,
            source="dashboard",
            stt_client=fake_stt,
        )

    assert result == {"status": "completed", "job_id": job_id, "voice_note_id": 1}
    assert fake_stt.calls == 1

    with session_factory() as db:
        voice_note = db.scalar(select(VoiceNote).where(VoiceNote.media_file_id == media_id))
        transaction = db.scalar(select(Transaction))
        job = db.get(Job, job_id)
        assert voice_note is not None
        assert voice_note.transcript_text == "beli makan dua puluh ribu"
        assert voice_note.stt_provider == "google_speech_to_text"
        assert voice_note.status == "processed"
        assert transaction is not None
        assert transaction.source == "voice_note"
        assert transaction.amount == Decimal("20000.00")
        assert voice_note.transaction_id == transaction.id
        assert job is not None
        assert job.status == "completed"
        assert job.result_id == voice_note.id


def test_voice_stt_worker_marks_ambiguous_transcript_for_clarification(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeSttClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_stt, _queued_jobs = test_client
    fake_stt.text = "beli makan"
    token = _register_and_login(client, "owner@example.com")
    media_id = _upload_audio(client, token, duration_seconds=10)
    queue_response = client.post(
        f"/api/stt/transcribe/{media_id}",
        headers=_auth_headers(token),
    )
    job_id = int(queue_response.json()["job"]["id"])
    user_id = int(queue_response.json()["job"]["user_id"])

    with session_factory() as db:
        run_voice_stt_job(
            db,
            job_id=job_id,
            user_id=user_id,
            media_id=media_id,
            source="dashboard",
            stt_client=fake_stt,
        )

    with session_factory() as db:
        voice_note = db.scalar(select(VoiceNote).where(VoiceNote.media_file_id == media_id))
        assert voice_note is not None
        assert voice_note.transcript_text == "beli makan"
        assert voice_note.status == "needs_confirmation"
        assert voice_note.transaction_id is None
        assert db.scalar(select(Transaction)) is None


def test_voice_stt_rejects_audio_over_30_seconds(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeSttClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, _session_factory, fake_stt, queued_jobs = test_client
    token = _register_and_login(client, "owner@example.com")
    media_id = _upload_audio(client, token, duration_seconds=31)

    response = client.post(
        f"/api/stt/transcribe/{media_id}",
        headers=_auth_headers(token),
    )

    assert response.status_code == 413
    assert "exceeds 30 seconds" in response.json()["detail"]
    assert fake_stt.calls == 0
    assert queued_jobs == []


def test_voice_stt_worker_marks_job_failed_on_google_api_error(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeSttClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_stt, _queued_jobs = test_client
    token = _register_and_login(client, "owner@example.com")
    media_id = _upload_audio(client, token, duration_seconds=10)
    queue_response = client.post(
        f"/api/stt/transcribe/{media_id}",
        headers=_auth_headers(token),
    )
    job_id = int(queue_response.json()["job"]["id"])
    user_id = int(queue_response.json()["job"]["user_id"])
    fake_stt.error = SttClientError("Google Speech-to-Text quota exceeded", status_code=503)

    with pytest.raises(SttClientError):
        with session_factory() as db:
            run_voice_stt_job(
                db,
                job_id=job_id,
                user_id=user_id,
                media_id=media_id,
                source="dashboard",
                stt_client=fake_stt,
            )

    with session_factory() as db:
        voice_note = db.scalar(select(VoiceNote).where(VoiceNote.media_file_id == media_id))
        job = db.get(Job, job_id)
        assert voice_note is not None
        assert voice_note.transcript_text is None
        assert voice_note.status == "error"
        assert job is not None
        assert job.status == "failed"
        assert job.error_message == "Google Speech-to-Text quota exceeded"


def _upload_audio(client: TestClient, token: str, *, duration_seconds: int) -> int:
    response = client.post(
        "/api/media",
        headers=_auth_headers(token),
        data={"file_type": "audio", "source": "dashboard_upload"},
        files={
            "file": (
                "voice.ogg",
                _ogg_opus_bytes(duration_seconds=duration_seconds),
                "audio/ogg",
            )
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def _ogg_opus_bytes(*, duration_seconds: int) -> bytes:
    granule_position = duration_seconds * 48_000
    return (
        b"OggS"
        + bytes([0, 0])
        + granule_position.to_bytes(8, "little", signed=True)
        + (1).to_bytes(4, "little")
        + (0).to_bytes(4, "little")
        + (0).to_bytes(4, "little")
        + bytes([0])
    )


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
