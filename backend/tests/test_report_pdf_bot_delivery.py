import os
from collections.abc import Iterator
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
from app.models import Category, Job, MediaFile, Report, User, UserPlatformAccount
from app.modules.jobs.service import get_report_pdf_enqueue
from app.modules.media.service import resolve_media_file_path
from app.modules.reports.pdf import ReportPdfError
from app.modules.telegram.client import get_telegram_client
from app.modules.waha.client import get_waha_client
from app.workers.tasks import run_report_pdf_job


class FakePdfRenderer:
    def __init__(self, *, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.html: str | None = None

    def render_html(self, html: str) -> bytes:
        self.html = html
        if self.should_fail:
            raise ReportPdfError("renderer_down")
        return b"%PDF-1.4\n% bot export pdf\n"


class FakeWahaClient:
    def __init__(self) -> None:
        self.session = "default"
        self.sent_messages: list[dict[str, str]] = []
        self.sent_files: list[dict[str, Any]] = []

    def send_text(
        self,
        *,
        chat_id: str,
        text: str,
        session: str | None = None,
    ) -> dict[str, Any]:
        self.sent_messages.append(
            {"chat_id": chat_id, "text": text, "session": session or self.session}
        )
        return {"id": len(self.sent_messages)}

    def send_file(
        self,
        *,
        chat_id: str,
        filename: str,
        mimetype: str = "application/pdf",
        file_data: bytes | str | None = None,
        caption: str | None = None,
        session: str | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        self.sent_files.append(
            {
                "chat_id": chat_id,
                "filename": filename,
                "mimetype": mimetype,
                "file_data": file_data,
                "caption": caption,
                "session": session or self.session,
            }
        )
        return {"id": len(self.sent_files)}


class FakeTelegramClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, str]] = []
        self.sent_documents: list[dict[str, Any]] = []

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

    def send_document(
        self,
        *,
        chat_id: str,
        file_content: bytes,
        filename: str,
        caption: str | None = None,
        parse_mode: str | None = None,
    ) -> dict[str, Any]:
        self.sent_documents.append(
            {
                "chat_id": chat_id,
                "file_content": file_content,
                "filename": filename,
                "caption": caption,
                "parse_mode": parse_mode or "",
            }
        )
        return {"ok": True, "result": {"message_id": len(self.sent_documents)}}


@pytest.fixture()
def test_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[
    tuple[
        TestClient,
        sessionmaker[Session],
        FakeWahaClient,
        FakeTelegramClient,
        list[dict[str, Any]],
    ]
]:
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "storage"))
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
                Category(name="Gaji", type="income"),
            ]
        )
        db.commit()

    fake_waha_client = FakeWahaClient()
    fake_telegram_client = FakeTelegramClient()
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
    app.dependency_overrides[get_telegram_client] = lambda: fake_telegram_client
    app.dependency_overrides[get_report_pdf_enqueue] = lambda: fake_enqueue

    with TestClient(app) as client:
        yield (
            client,
            TestingSessionLocal,
            fake_waha_client,
            fake_telegram_client,
            queued_jobs,
        )

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    get_settings.cache_clear()


def test_waha_export_laporan_bulan_ini_queues_pdf_and_sends_file(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeWahaClient,
        FakeTelegramClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_waha, _fake_telegram, queued_jobs = test_client
    _create_linked_whatsapp_user(session_factory)

    response = client.post("/webhook/waha", json=_waha_text_update("export laporan bulan ini"))

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["message_type"] == "report_pdf"
    assert payload["transaction_status"] == "queued"
    assert payload["job_id"] is not None
    assert payload["reply_status"] == "sent"
    assert "export PDF laporan bulan ini" in fake_waha.sent_messages[-1]["text"]
    assert queued_jobs[0]["period"] == "month"
    assert queued_jobs[0]["notify_platform"] == "whatsapp"
    assert queued_jobs[0]["notify_chat_id"] == "6281234567890@c.us"

    renderer = FakePdfRenderer()
    with session_factory() as db:
        result = run_report_pdf_job(
            db,
            job_id=queued_jobs[0]["job_id"],
            user_id=queued_jobs[0]["user_id"],
            period=queued_jobs[0]["period"],
            source=queued_jobs[0]["source"],
            anchor_date=queued_jobs[0]["anchor_date"],
            renderer=renderer,
            waha_client=fake_waha,
            notify_chat_id=queued_jobs[0]["notify_chat_id"],
            notify_session=queued_jobs[0]["notify_session"],
            notify_platform=queued_jobs[0]["notify_platform"],
        )

    assert result["status"] == "completed"
    assert fake_waha.sent_files
    sent_file = fake_waha.sent_files[-1]
    assert sent_file["mimetype"] == "application/pdf"
    assert sent_file["file_data"].startswith(b"%PDF-1.4")
    assert "Laporan PDF siap" in sent_file["caption"]

    with session_factory() as db:
        job = db.get(Job, queued_jobs[0]["job_id"])
        report = db.scalar(select(Report))
        media_file = db.scalar(select(MediaFile))
        assert job is not None
        assert job.status == "completed"
        assert report is not None
        assert report.generated_from == "whatsapp_bot"
        assert media_file is not None
        assert resolve_media_file_path(media_file).read_bytes().startswith(b"%PDF-1.4")


def test_telegram_export_laporan_bulan_ini_queues_pdf_and_sends_document(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeWahaClient,
        FakeTelegramClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, _fake_waha, fake_telegram, queued_jobs = test_client
    _create_linked_telegram_user(session_factory)

    response = _post_telegram_update(
        client,
        update=_telegram_text_update("export laporan bulan ini"),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["message_type"] == "report_pdf"
    assert payload["transaction_status"] == "queued"
    assert payload["job_id"] is not None
    assert "export PDF laporan bulan ini" in fake_telegram.sent_messages[-1]["text"]
    assert queued_jobs[0]["period"] == "month"
    assert queued_jobs[0]["notify_platform"] == "telegram"
    assert queued_jobs[0]["notify_chat_id"] == "456"

    with session_factory() as db:
        run_report_pdf_job(
            db,
            job_id=queued_jobs[0]["job_id"],
            user_id=queued_jobs[0]["user_id"],
            period=queued_jobs[0]["period"],
            source=queued_jobs[0]["source"],
            anchor_date=queued_jobs[0]["anchor_date"],
            renderer=FakePdfRenderer(),
            telegram_client=fake_telegram,
            notify_chat_id=queued_jobs[0]["notify_chat_id"],
            notify_platform=queued_jobs[0]["notify_platform"],
        )

    assert fake_telegram.sent_documents
    document = fake_telegram.sent_documents[-1]
    assert document["chat_id"] == "456"
    assert document["file_content"].startswith(b"%PDF-1.4")
    assert document["filename"].endswith(".pdf")
    assert "Laporan PDF siap" in document["caption"]


def test_pdf_worker_failure_sends_error_message_to_telegram(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeWahaClient,
        FakeTelegramClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, _fake_waha, fake_telegram, queued_jobs = test_client
    _create_linked_telegram_user(session_factory)

    response = _post_telegram_update(
        client,
        update=_telegram_text_update("export laporan bulan ini"),
    )
    assert response.status_code == 200, response.text

    with pytest.raises(ReportPdfError):
        with session_factory() as db:
            run_report_pdf_job(
                db,
                job_id=queued_jobs[0]["job_id"],
                user_id=queued_jobs[0]["user_id"],
                period=queued_jobs[0]["period"],
                source=queued_jobs[0]["source"],
                anchor_date=queued_jobs[0]["anchor_date"],
                renderer=FakePdfRenderer(should_fail=True),
                telegram_client=fake_telegram,
                notify_chat_id=queued_jobs[0]["notify_chat_id"],
                notify_platform=queued_jobs[0]["notify_platform"],
            )

    assert "PDF laporan gagal dibuat" in fake_telegram.sent_messages[-1]["text"]

    with session_factory() as db:
        job = db.get(Job, queued_jobs[0]["job_id"])
        report = db.scalar(select(Report))
        assert job is not None
        assert job.status == "failed"
        assert "renderer_down" in (job.error_message or "")
        assert report is not None
        assert report.status == "failed"


def _post_telegram_update(client: TestClient, *, update: dict[str, Any]) -> Any:
    return client.post(
        "/webhook/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-telegram-secret"},
        json=update,
    )


def _create_linked_whatsapp_user(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as db:
        user = User(
            name="WA User",
            email="wa-report@example.com",
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


def _create_linked_telegram_user(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as db:
        user = User(
            name="Telegram User",
            email="telegram-report@example.com",
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


def _waha_text_update(text: str) -> dict[str, Any]:
    return {
        "event": "message",
        "session": "default",
        "payload": {
            "id": "msg-text-1",
            "from": "6281234567890@c.us",
            "fromMe": False,
            "type": "chat",
            "body": text,
        },
    }


def _telegram_text_update(text: str) -> dict[str, Any]:
    return {
        "update_id": 1002,
        "message": {
            "message_id": 20,
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
            "text": text,
        },
    }
