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
os.environ["TELEGRAM_BOT_TOKEN"] = "123456:test-token"
os.environ["TELEGRAM_WEBHOOK_SECRET"] = "test-telegram-secret"

from app.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import Category, Job, MediaFile, Transaction, User, UserPlatformAccount, VoiceNote
from app.modules.jobs.service import get_voice_stt_enqueue
from app.modules.stt.client import SttResult
from app.modules.telegram.client import DownloadedTelegramFile, get_telegram_client
from app.workers.tasks import run_voice_stt_job


class FakeTelegramClient:
    def __init__(self) -> None:
        self.downloaded_media = DownloadedTelegramFile(
            content=_ogg_opus_bytes(duration_seconds=10),
            content_type="audio/ogg",
            filename="voice.ogg",
        )
        self.downloaded_file_ids: list[str] = []
        self.sent_messages: list[dict[str, str]] = []

    def send_message(
        self,
        *,
        chat_id: str,
        text: str,
        parse_mode: str | None = None,
    ) -> dict[str, Any]:
        self.sent_messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode or "",
            }
        )
        return {"ok": True, "result": {"message_id": len(self.sent_messages)}}

    def download_media(
        self,
        *,
        file_id: str,
        fallback_filename: str | None = None,
        fallback_content_type: str | None = None,
    ) -> DownloadedTelegramFile:
        self.downloaded_file_ids.append(file_id)
        return self.downloaded_media


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
        FakeTelegramClient,
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

    fake_telegram_client = FakeTelegramClient()
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
    app.dependency_overrides[get_telegram_client] = lambda: fake_telegram_client
    app.dependency_overrides[get_voice_stt_enqueue] = lambda: fake_enqueue

    with TestClient(app) as client:
        yield client, TestingSessionLocal, fake_telegram_client, fake_stt_client, queued_jobs

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    get_settings.cache_clear()


def test_telegram_voice_note_is_queued_then_transcribed(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeTelegramClient,
        FakeSttClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_telegram, fake_stt, queued_jobs = test_client
    _create_linked_telegram_user(session_factory)

    response = _post_telegram_update(
        client,
        update=_telegram_voice_update(duration_seconds=10),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["message_type"] == "voice_stt"
    assert payload["transaction_status"] == "queued"
    assert payload["job_id"] is not None
    assert payload["reply_status"] == "sent"
    assert fake_telegram.downloaded_file_ids == ["telegram-voice-file-id"]
    assert "antrean transkripsi" in fake_telegram.sent_messages[-1]["text"]

    with session_factory() as db:
        media_file = db.scalar(select(MediaFile))
        job = db.scalar(select(Job))
        assert media_file is not None
        assert media_file.file_type == "audio"
        assert media_file.source == "telegram_voice"
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
            telegram_client=fake_telegram,
            notify_chat_id=queued_jobs[0]["notify_chat_id"],
            notify_platform=queued_jobs[0]["notify_platform"],
        )

    assert fake_stt.calls == 1
    assert "Voice note selesai ditranskrip" in fake_telegram.sent_messages[-1]["text"]

    with session_factory() as db:
        voice_note = db.scalar(select(VoiceNote))
        transaction = db.scalar(select(Transaction))
        assert voice_note is not None
        assert voice_note.transcript_text == "beli makan dua puluh ribu"
        assert voice_note.status == "processed"
        assert transaction is not None
        assert transaction.source == "voice_note"
        assert transaction.amount == Decimal("20000.00")


def test_telegram_voice_note_ambiguous_transcript_asks_for_clarification(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeTelegramClient,
        FakeSttClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_telegram, fake_stt, queued_jobs = test_client
    fake_stt.text = "beli makan"
    _create_linked_telegram_user(session_factory)

    response = _post_telegram_update(
        client,
        update=_telegram_voice_update(duration_seconds=10),
    )
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
            telegram_client=fake_telegram,
            notify_chat_id=queued_jobs[0]["notify_chat_id"],
            notify_platform=queued_jobs[0]["notify_platform"],
        )

    assert "Saya belum yakin membaca transaksinya" in fake_telegram.sent_messages[-1]["text"]

    with session_factory() as db:
        voice_note = db.scalar(select(VoiceNote))
        assert voice_note is not None
        assert voice_note.status == "needs_confirmation"
        assert voice_note.transaction_id is None
        assert db.scalar(select(Transaction)) is None


def test_telegram_voice_note_over_30_seconds_is_rejected_before_download(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeTelegramClient,
        FakeSttClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_telegram, fake_stt, queued_jobs = test_client
    _create_linked_telegram_user(session_factory)

    response = _post_telegram_update(
        client,
        update=_telegram_voice_update(duration_seconds=31),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["message_type"] == "voice_stt"
    assert payload["transaction_status"] == "duration_rejected"
    assert "maksimal 30 detik" in fake_telegram.sent_messages[-1]["text"]
    assert fake_telegram.downloaded_file_ids == []
    assert fake_stt.calls == 0
    assert queued_jobs == []


def _post_telegram_update(client: TestClient, *, update: dict[str, Any]) -> Any:
    return client.post(
        "/webhook/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-telegram-secret"},
        json=update,
    )


def _create_linked_telegram_user(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as db:
        user = User(
            name="Telegram User",
            email="telegram-voice@example.com",
            password_hash="hashed-password",
        )
        db.add(user)
        db.flush()
        db.add(
            UserPlatformAccount(
                user_id=user.id,
                platform="telegram",
                platform_user_id="123",
                chat_id="456",
            )
        )
        db.commit()


def _telegram_voice_update(*, duration_seconds: int) -> dict[str, Any]:
    return {
        "update_id": 1001,
        "message": {
            "message_id": 10,
            "from": {
                "id": 123,
                "is_bot": False,
                "first_name": "Tester",
                "username": "tester",
            },
            "chat": {
                "id": 456,
                "first_name": "Tester",
                "username": "tester",
                "type": "private",
            },
            "date": 1760000000,
            "voice": {
                "file_id": "telegram-voice-file-id",
                "file_unique_id": "telegram-voice-unique-id",
                "duration": duration_seconds,
                "mime_type": "audio/ogg",
                "file_size": 128,
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
