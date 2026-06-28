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
from app.models import Category, Job, MediaFile, Transaction, User, UserPlatformAccount, VoiceNote
from app.modules.jobs.service import get_voice_stt_enqueue
from app.modules.stt.client import SttResult
from app.modules.waha.client import DownloadedMedia, get_waha_client
from app.workers.tasks import run_voice_stt_job


class FakeWahaClient:
    def __init__(self) -> None:
        self.session = "default"
        self.downloaded_media = DownloadedMedia(
            content=_ogg_opus_bytes(duration_seconds=10),
            content_type="audio/ogg",
            filename="voice.ogg",
        )
        self.downloaded_urls: list[str] = []
        self.sent_messages: list[dict[str, str]] = []

    def download_media(self, media_url: str) -> DownloadedMedia:
        self.downloaded_urls.append(media_url)
        return self.downloaded_media

    def send_text(
        self,
        *,
        chat_id: str,
        text: str,
        session: str | None = None,
    ) -> dict[str, Any]:
        self.sent_messages.append({"chat_id": chat_id, "text": text})
        return {"id": len(self.sent_messages), "session": session or self.session}


class FakeSttClient:
    def __init__(self) -> None:
        self.calls = 0
        self.text = "beli makan dua puluh ribu"

    def transcribe(
        self,
        audio_content: bytes,
        *,
        mime_type: str | None = None,
        sample_rate_hertz: int | None = None,
    ) -> SttResult:
        self.calls += 1
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
        FakeWahaClient,
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

    fake_waha_client = FakeWahaClient()
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
    app.dependency_overrides[get_waha_client] = lambda: fake_waha_client
    app.dependency_overrides[get_voice_stt_enqueue] = lambda: fake_enqueue

    with TestClient(app) as client:
        yield client, TestingSessionLocal, fake_waha_client, fake_stt_client, queued_jobs

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    get_settings.cache_clear()


def test_waha_voice_note_is_queued_then_transcribed(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeWahaClient,
        FakeSttClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_waha, fake_stt, queued_jobs = test_client
    _create_linked_whatsapp_user(session_factory)

    response = client.post("/webhook/waha", json=_waha_audio_update(duration_seconds=10))

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["message_type"] == "voice_stt"
    assert payload["transaction_status"] == "queued"
    assert payload["job_id"] is not None
    assert payload["reply_status"] == "sent"
    assert fake_waha.downloaded_urls == ["https://waha.local/media/voice-1"]
    assert "antrean transkripsi" in fake_waha.sent_messages[-1]["text"]

    with session_factory() as db:
        media_file = db.scalar(select(MediaFile))
        job = db.scalar(select(Job))
        assert media_file is not None
        assert media_file.file_type == "audio"
        assert media_file.source == "whatsapp_voice"
        assert job is not None
        assert job.status == "queued"
        assert db.scalar(select(VoiceNote)) is None

    with session_factory() as db:
        run_voice_stt_job(
            db,
            job_id=queued_jobs[0]["job_id"],
            user_id=queued_jobs[0]["user_id"],
            media_id=queued_jobs[0]["media_id"],
            source=queued_jobs[0]["source"],
            duration_seconds=queued_jobs[0]["duration_seconds"],
            stt_client=fake_stt,
            waha_client=fake_waha,
            notify_chat_id=queued_jobs[0]["notify_chat_id"],
            notify_session=queued_jobs[0]["notify_session"],
            notify_platform=queued_jobs[0]["notify_platform"],
        )

    assert fake_stt.calls == 1
    assert "Voice note selesai ditranskrip" in fake_waha.sent_messages[-1]["text"]

    with session_factory() as db:
        voice_note = db.scalar(select(VoiceNote))
        transaction = db.scalar(select(Transaction))
        assert voice_note is not None
        assert voice_note.transcript_text == "beli makan dua puluh ribu"
        assert voice_note.status == "processed"
        assert transaction is not None
        assert transaction.source == "voice_note"
        assert transaction.amount == Decimal("20000.00")


def test_waha_voice_note_ambiguous_transcript_asks_for_clarification(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeWahaClient,
        FakeSttClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_waha, fake_stt, queued_jobs = test_client
    fake_stt.text = "beli makan"
    _create_linked_whatsapp_user(session_factory)

    response = client.post("/webhook/waha", json=_waha_audio_update(duration_seconds=10))
    assert response.status_code == 200, response.text

    with session_factory() as db:
        run_voice_stt_job(
            db,
            job_id=queued_jobs[0]["job_id"],
            user_id=queued_jobs[0]["user_id"],
            media_id=queued_jobs[0]["media_id"],
            source=queued_jobs[0]["source"],
            duration_seconds=queued_jobs[0]["duration_seconds"],
            stt_client=fake_stt,
            waha_client=fake_waha,
            notify_chat_id=queued_jobs[0]["notify_chat_id"],
            notify_session=queued_jobs[0]["notify_session"],
            notify_platform=queued_jobs[0]["notify_platform"],
        )

    assert "Saya belum yakin membaca transaksinya" in fake_waha.sent_messages[-1]["text"]

    with session_factory() as db:
        voice_note = db.scalar(select(VoiceNote))
        assert voice_note is not None
        assert voice_note.status == "needs_confirmation"
        assert voice_note.transaction_id is None
        assert db.scalar(select(Transaction)) is None


def test_waha_voice_note_over_30_seconds_is_rejected_before_download(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeWahaClient,
        FakeSttClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, _session_factory, fake_waha, fake_stt, queued_jobs = test_client
    _create_linked_whatsapp_user(_session_factory)

    response = client.post("/webhook/waha", json=_waha_audio_update(duration_seconds=31))

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["message_type"] == "voice_stt"
    assert payload["transaction_status"] == "duration_rejected"
    assert "maksimal 30 detik" in fake_waha.sent_messages[-1]["text"]
    assert fake_waha.downloaded_urls == []
    assert fake_stt.calls == 0
    assert queued_jobs == []


def _create_linked_whatsapp_user(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as db:
        user = User(
            name="WA User",
            email="wa@example.com",
            password_hash="hashed-password",
        )
        db.add(user)
        db.flush()
        db.add(
            UserPlatformAccount(
                user_id=user.id,
                platform="whatsapp",
                platform_user_id="6281234567890",
                phone_number="6281234567890",
                chat_id="6281234567890@c.us",
            )
        )
        db.commit()


def _waha_audio_update(*, duration_seconds: int) -> dict[str, Any]:
    return {
        "event": "message",
        "session": "default",
        "payload": {
            "id": "msg-audio-1",
            "from": "6281234567890@c.us",
            "fromMe": False,
            "hasMedia": True,
            "type": "ptt",
            "duration": duration_seconds,
            "media": {
                "url": "https://waha.local/media/voice-1",
                "mimetype": "audio/ogg",
                "filename": "voice.ogg",
            },
        },
    }


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
