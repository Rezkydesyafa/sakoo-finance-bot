import os
from collections.abc import Iterator
from datetime import date, timedelta
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
from app.models import (
    BotLog,
    Category,
    Job,
    MediaFile,
    Receipt,
    Transaction,
    User,
    UserPlatformAccount,
)
from app.modules.jobs.service import get_receipt_ocr_enqueue
from app.modules.ocr.client import OcrResult
from app.modules.waha.client import DownloadedMedia, get_waha_client
from app.workers.tasks import run_receipt_ocr_job


class FakeWahaClient:
    def __init__(self) -> None:
        self.session = "default"
        self.downloaded_media = DownloadedMedia(
            content=b"fake-receipt-image",
            content_type="image/jpeg",
            filename="receipt.jpg",
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


class FakeOcrClient:
    def __init__(self) -> None:
        self.text = "TOKO SAKOO\n27/06/2026\nTOTAL BAYAR Rp 20.000"
        self.calls = 0

    def extract_text(self, image_content: bytes) -> OcrResult:
        self.calls += 1
        assert image_content == b"fake-receipt-image"
        return OcrResult(text=self.text)


@pytest.fixture()
def test_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[
    tuple[
        TestClient,
        sessionmaker[Session],
        FakeWahaClient,
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

    with TestingSessionLocal() as db:
        db.add_all(
            [
                Category(name="Lainnya", type="expense"),
                Category(name="Transportasi", type="expense"),
            ]
        )
        db.commit()

    fake_waha_client = FakeWahaClient()
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
    app.dependency_overrides[get_waha_client] = lambda: fake_waha_client
    app.dependency_overrides[get_receipt_ocr_enqueue] = lambda: fake_enqueue

    with TestClient(app) as client:
        yield client, TestingSessionLocal, fake_waha_client, fake_ocr_client, queued_jobs

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    get_settings.cache_clear()


def test_waha_receipt_image_is_queued_then_processed_and_confirmed(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeWahaClient,
        FakeOcrClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_waha, fake_ocr, queued_jobs = test_client
    _create_linked_whatsapp_user(session_factory)

    image_response = client.post("/webhook/waha", json=_waha_image_update())

    assert image_response.status_code == 200, image_response.text
    image_payload = image_response.json()
    assert image_payload["message_type"] == "receipt_ocr"
    assert image_payload["transaction_status"] == "queued"
    assert image_payload["transaction_id"] is None
    assert image_payload["receipt_id"] is not None
    assert image_payload["job_id"] is not None
    assert image_payload["reply_status"] == "sent"
    assert fake_waha.downloaded_urls == ["https://waha.local/media/receipt-1"]
    assert fake_ocr.calls == 0
    assert "masuk antrean OCR" in fake_waha.sent_messages[-1]["text"]

    with session_factory() as db:
        media_file = db.scalar(select(MediaFile))
        job = db.scalar(select(Job))
        assert media_file is not None
        assert media_file.file_type == "receipt"
        assert media_file.source == "whatsapp_receipt"
        assert job is not None
        assert job.status == "queued"
        assert job.result_id is None
        receipt = db.scalar(select(Receipt))
        assert receipt is not None
        assert receipt.status == "pending"
        assert receipt.caption_text is None

    _run_queued_ocr_job(session_factory, fake_ocr, fake_waha, queued_jobs[0])

    assert fake_ocr.calls == 1
    assert "Balas YA" in fake_waha.sent_messages[-1]["text"]

    with session_factory() as db:
        receipt = db.scalar(select(Receipt))
        job = db.scalar(select(Job))
        assert receipt is not None
        assert receipt.merchant_name == "TOKO SAKOO"
        assert receipt.total_amount == Decimal("20000.00")
        assert receipt.transaction_id is None
        assert job is not None
        assert job.status == "completed"
        assert job.result_id == receipt.id
        assert db.scalar(select(Transaction)) is None

    confirm_response = client.post("/webhook/waha", json=_waha_text_update("YA"))

    assert confirm_response.status_code == 200, confirm_response.text
    confirm_payload = confirm_response.json()
    assert confirm_payload["message_type"] == "receipt_ocr"
    assert confirm_payload["transaction_status"] == "saved"
    assert confirm_payload["transaction_id"] is not None
    assert "Transaksi struk tersimpan" in fake_waha.sent_messages[-1]["text"]
    assert "Lihat dashboard:" in fake_waha.sent_messages[-1]["text"]

    with session_factory() as db:
        transaction = db.scalar(select(Transaction))
        receipt = db.scalar(select(Receipt))
        assert transaction is not None
        assert transaction.source == "receipt_ocr"
        assert transaction.type == "expense"
        assert transaction.amount == Decimal("20000.00")
        assert transaction.description == "Struk TOKO SAKOO"
        assert receipt is not None
        assert receipt.status == "confirmed"
        assert receipt.transaction_id == transaction.id


def test_waha_receipt_total_can_be_edited_after_worker_confirmation(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeWahaClient,
        FakeOcrClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_waha, fake_ocr, queued_jobs = test_client
    _create_linked_whatsapp_user(session_factory)
    fake_ocr.text = "TOKO SAKOO\nKopi Rp 12.000\nRoti Rp 8.000"

    image_response = client.post("/webhook/waha", json=_waha_image_update())
    assert image_response.status_code == 200, image_response.text
    assert image_response.json()["transaction_status"] == "queued"

    _run_queued_ocr_job(session_factory, fake_ocr, fake_waha, queued_jobs[0])

    assert "Total belum terbaca" in fake_waha.sent_messages[-1]["text"]
    assert "Tanggal tidak jelas" in fake_waha.sent_messages[-1]["text"]
    assert "Foto agak blur" in fake_waha.sent_messages[-1]["text"]
    assert "edit total" in fake_waha.sent_messages[-1]["text"].lower()
    assert "Item: Kopi, Roti" in fake_waha.sent_messages[-1]["text"]

    edit_response = client.post("/webhook/waha", json=_waha_text_update("21000"))
    assert edit_response.status_code == 200, edit_response.text
    assert edit_response.json()["transaction_status"] == "edit_updated"
    assert "Rp21.000" in fake_waha.sent_messages[-1]["text"]

    confirm_response = client.post("/webhook/waha", json=_waha_text_update("YA"))
    assert confirm_response.status_code == 200, confirm_response.text
    assert confirm_response.json()["transaction_status"] == "saved"

    with session_factory() as db:
        transaction = db.scalar(select(Transaction))
        receipt = db.scalar(select(Receipt))
        assert transaction is not None
        assert transaction.amount == Decimal("21000.00")
        assert transaction.description == "Kopi, Roti"
        assert receipt is not None
        assert receipt.status == "confirmed"
        assert receipt.transaction_id == transaction.id


def test_waha_receipt_double_confirmation_does_not_duplicate_transaction(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeWahaClient,
        FakeOcrClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_waha, fake_ocr, queued_jobs = test_client
    _create_linked_whatsapp_user(session_factory)

    client.post("/webhook/waha", json=_waha_image_update())
    _run_queued_ocr_job(session_factory, fake_ocr, fake_waha, queued_jobs[0])
    first_confirm = client.post("/webhook/waha", json=_waha_text_update("YA"))
    second_confirm = client.post("/webhook/waha", json=_waha_text_update("YA"))

    assert first_confirm.status_code == 200, first_confirm.text
    assert first_confirm.json()["transaction_status"] == "saved"
    assert second_confirm.status_code == 200, second_confirm.text
    assert second_confirm.json()["transaction_status"] == "duplicate"
    assert "tidak simpan lagi" in fake_waha.sent_messages[-1]["text"]

    with session_factory() as db:
        transactions = db.scalars(select(Transaction)).all()
        assert len(transactions) == 1


def test_waha_receipt_duplicate_ocr_result_is_not_saved_twice(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeWahaClient,
        FakeOcrClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_waha, _fake_ocr, _queued_jobs = test_client
    _create_linked_whatsapp_user(session_factory)

    with session_factory() as db:
        user = db.scalar(select(User))
        category = db.scalar(select(Category).where(Category.name == "Lainnya"))
        assert user is not None
        transaction = Transaction(
            user_id=user.id,
            type="expense",
            amount=Decimal("20000.00"),
            category_id=category.id if category else None,
            description="Struk TOKO SAKOO",
            transaction_date=date(2026, 6, 27),
            source="receipt_ocr",
        )
        media_file = MediaFile(
            user_id=user.id,
            file_type="receipt",
            original_filename="duplicate.jpg",
            stored_path="receipts/duplicate.jpg",
            mime_type="image/jpeg",
            size=10,
            source="whatsapp_receipt",
        )
        db.add_all([transaction, media_file])
        db.flush()
        db.add(
            Receipt(
                user_id=user.id,
                media_file_id=media_file.id,
                merchant_name="TOKO SAKOO",
                receipt_date=date(2026, 6, 27),
                total_amount=Decimal("20000.00"),
                confidence=Decimal("1.0000"),
                status="processed",
            )
        )
        db.commit()

    response = client.post("/webhook/waha", json=_waha_text_update("YA"))

    assert response.status_code == 200, response.text
    assert response.json()["transaction_status"] == "duplicate"
    assert "tidak simpan lagi" in fake_waha.sent_messages[-1]["text"]

    with session_factory() as db:
        transactions = db.scalars(select(Transaction)).all()
        receipt = db.scalar(select(Receipt))
        assert len(transactions) == 1
        assert receipt is not None
        assert receipt.status == "duplicate"
        assert receipt.transaction_id == transactions[0].id


def test_waha_receipt_can_edit_category_date_merchant_and_note(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeWahaClient,
        FakeOcrClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_waha, _fake_ocr, _queued_jobs = test_client
    _create_linked_whatsapp_user(session_factory)
    yesterday = date.today() - timedelta(days=1)

    with session_factory() as db:
        user = db.scalar(select(User))
        assert user is not None
        media_file = MediaFile(
            user_id=user.id,
            file_type="receipt",
            original_filename="receipt.jpg",
            stored_path="receipts/edit.jpg",
            mime_type="image/jpeg",
            size=10,
            source="whatsapp_receipt",
        )
        db.add(media_file)
        db.flush()
        db.add(
            Receipt(
                user_id=user.id,
                media_file_id=media_file.id,
                merchant_name="WARUNG AI",
                total_amount=Decimal("15415.00"),
                confidence=Decimal("1.0000"),
                status="processed",
            )
        )
        db.commit()

    for text, expected in [
        ("edit kategori transport", "Transportasi"),
        ("edit tanggal kemarin", yesterday.isoformat()),
        ("edit merchant Indomaret", "Indomaret"),
        ("edit catatan parkir kantor", "parkir kantor"),
        ("/edit beli kopi", "beli kopi"),
    ]:
        response = client.post("/webhook/waha", json=_waha_text_update(text))
        assert response.status_code == 200, response.text
        assert response.json()["transaction_status"] == "edit_updated"
        assert expected in fake_waha.sent_messages[-1]["text"]

    confirm_response = client.post("/webhook/waha", json=_waha_text_update("YA"))

    assert confirm_response.status_code == 200, confirm_response.text
    assert confirm_response.json()["transaction_status"] == "saved"
    with session_factory() as db:
        transaction = db.scalar(select(Transaction))
        receipt = db.scalar(select(Receipt))
        assert transaction is not None
        assert transaction.category is not None
        assert transaction.category.name == "Transportasi"
        assert transaction.transaction_date == yesterday
        assert transaction.description == "beli kopi"
        assert receipt is not None
        assert receipt.merchant_name == "Indomaret"


def test_waha_receipt_caption_is_used_when_ocr_total_is_missing(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeWahaClient,
        FakeOcrClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_waha, fake_ocr, queued_jobs = test_client
    _create_linked_whatsapp_user(session_factory)
    fake_ocr.text = "TOKO SAKOO\nKopi dan roti"

    image_response = client.post(
        "/webhook/waha",
        json=_waha_image_update(caption="beli kopi 18 ribu"),
    )
    assert image_response.status_code == 200, image_response.text
    assert "Aku lagi baca struknya" in fake_waha.sent_messages[-1]["text"]

    _run_queued_ocr_job(session_factory, fake_ocr, fake_waha, queued_jobs[0])

    assert "caption" in fake_waha.sent_messages[-1]["text"].lower()
    assert "Rp18.000" in fake_waha.sent_messages[-1]["text"]

    with session_factory() as db:
        receipt = db.scalar(select(Receipt))
        assert receipt is not None
        assert receipt.caption_text == "beli kopi 18 ribu"
        assert receipt.total_amount == Decimal("18000.00")
        assert receipt.status == "needs_confirmation"


def test_waha_receipt_without_caption_asks_and_saves_caption_reply(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeWahaClient,
        FakeOcrClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_waha, fake_ocr, queued_jobs = test_client
    _create_linked_whatsapp_user(session_factory)
    fake_ocr.text = "TOKO SAKOO\nKopi dan roti"

    image_response = client.post("/webhook/waha", json=_waha_image_update())
    assert image_response.status_code == 200, image_response.text
    assert "balas captionnya" in fake_waha.sent_messages[-1]["text"].lower()

    caption_response = client.post(
        "/webhook/waha",
        json=_waha_text_update("beli kopi 18 ribu"),
    )
    assert caption_response.status_code == 200, caption_response.text
    assert caption_response.json()["message_type"] == "receipt_ocr"
    assert caption_response.json()["transaction_status"] == "caption_saved"
    assert "keterangan struk sudah kusimpan" in fake_waha.sent_messages[-1]["text"]
    assert "Rp18.000" in fake_waha.sent_messages[-1]["text"]

    _run_queued_ocr_job(session_factory, fake_ocr, fake_waha, queued_jobs[0])

    with session_factory() as db:
        receipt = db.scalar(select(Receipt))
        assert receipt is not None
        assert receipt.caption_text == "beli kopi 18 ribu"
        assert receipt.total_amount == Decimal("18000.00")
        assert receipt.status == "needs_confirmation"
        assert db.scalar(select(Transaction)) is None


def test_waha_receipt_image_returns_limit_message_before_second_queue(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeWahaClient,
        FakeOcrClient,
        list[dict[str, Any]],
    ],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, session_factory, fake_waha, fake_ocr, queued_jobs = test_client
    monkeypatch.setenv("OCR_DAILY_LIMIT_PER_USER", "1")
    get_settings.cache_clear()
    _create_linked_whatsapp_user(session_factory)

    first_response = client.post("/webhook/waha", json=_waha_image_update())
    second_response = client.post("/webhook/waha", json=_waha_image_update())

    assert first_response.status_code == 200, first_response.text
    assert second_response.status_code == 200, second_response.text
    assert first_response.json()["transaction_status"] == "queued"
    assert second_response.json()["transaction_status"] == "limit_reached"
    assert fake_ocr.calls == 0
    assert len(queued_jobs) == 1
    assert "Batas OCR harian" in fake_waha.sent_messages[-1]["text"]

    with session_factory() as db:
        rate_limit_logs = db.scalars(
            select(BotLog)
            .where(
                BotLog.message_type == "receipt_ocr",
                BotLog.status.in_(("ocr_usage", "ocr_limit_reached")),
            )
            .order_by(BotLog.id)
        ).all()
        assert [log.status for log in rate_limit_logs] == [
            "ocr_usage",
            "ocr_limit_reached",
        ]
        assert db.scalar(select(Job).where(Job.status == "failed")) is None


def test_waha_from_me_message_is_logged_without_processing(
    test_client: tuple[
        TestClient,
        sessionmaker[Session],
        FakeWahaClient,
        FakeOcrClient,
        list[dict[str, Any]],
    ],
) -> None:
    client, session_factory, fake_waha, _fake_ocr, queued_jobs = test_client
    _create_linked_whatsapp_user(session_factory)

    response = client.post(
        "/webhook/waha",
        json=_waha_text_update("beli makan 20 ribu", from_me=True),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["linking_status"] == "from_me"
    assert payload["transaction_status"] is None
    assert payload["reply_status"] is None
    assert fake_waha.sent_messages == []
    assert queued_jobs == []

    with session_factory() as db:
        assert db.scalar(select(Transaction)) is None
        log = db.scalar(select(BotLog))
        assert log is not None
        assert log.status == "received"


def _run_queued_ocr_job(
    session_factory: sessionmaker[Session],
    fake_ocr: FakeOcrClient,
    fake_waha: FakeWahaClient,
    queued_job: dict[str, Any],
) -> None:
    with session_factory() as db:
        run_receipt_ocr_job(
            db,
            job_id=queued_job["job_id"],
            user_id=queued_job["user_id"],
            media_id=queued_job["media_id"],
            source=queued_job["source"],
            ocr_client=fake_ocr,
            waha_client=fake_waha,
            notify_chat_id=queued_job["notify_chat_id"],
            notify_session=queued_job["notify_session"],
        )


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


def _waha_image_update(caption: str | None = None) -> dict[str, Any]:
    payload = {
        "event": "message",
        "session": "default",
        "payload": {
            "id": "msg-image-1",
            "from": "6281234567890@c.us",
            "fromMe": False,
            "hasMedia": True,
            "type": "image",
            "media": {
                "url": "https://waha.local/media/receipt-1",
                "mimetype": "image/jpeg",
                "filename": "receipt.jpg",
            },
        },
    }
    if caption:
        payload["payload"]["caption"] = caption
    return payload


def _waha_text_update(text: str, *, from_me: bool = False) -> dict[str, Any]:
    return {
        "event": "message",
        "session": "default",
        "payload": {
            "id": f"msg-{text}",
            "from": "6281234567890@c.us",
            "fromMe": from_me,
            "body": text,
            "type": "text",
        },
    }
