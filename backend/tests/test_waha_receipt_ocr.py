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
from app.models import Category, Job, MediaFile, Receipt, Transaction, User, UserPlatformAccount
from app.modules.ocr.client import OcrResult, get_ocr_client
from app.modules.waha.client import DownloadedMedia, get_waha_client


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
) -> Iterator[tuple[TestClient, sessionmaker[Session], FakeWahaClient, FakeOcrClient]]:
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

    with TestingSessionLocal() as db:
        db.add(Category(name="Lainnya", type="expense"))
        db.commit()

    fake_waha_client = FakeWahaClient()
    fake_ocr_client = FakeOcrClient()

    def override_get_db() -> Iterator[Session]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_waha_client] = lambda: fake_waha_client
    app.dependency_overrides[get_ocr_client] = lambda: fake_ocr_client

    with TestClient(app) as client:
        yield client, TestingSessionLocal, fake_waha_client, fake_ocr_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    get_settings.cache_clear()


def test_waha_receipt_image_is_ocr_processed_and_confirmed(
    test_client: tuple[TestClient, sessionmaker[Session], FakeWahaClient, FakeOcrClient],
) -> None:
    client, session_factory, fake_waha, fake_ocr = test_client
    _create_linked_whatsapp_user(session_factory)

    image_response = client.post("/webhook/waha", json=_waha_image_update())

    assert image_response.status_code == 200, image_response.text
    image_payload = image_response.json()
    assert image_payload["message_type"] == "receipt_ocr"
    assert image_payload["transaction_status"] == "processed"
    assert image_payload["transaction_id"] is None
    assert image_payload["receipt_id"] is not None
    assert image_payload["job_id"] is not None
    assert image_payload["reply_status"] == "sent"
    assert fake_waha.downloaded_urls == ["https://waha.local/media/receipt-1"]
    assert fake_ocr.calls == 1
    assert "Ketik YA" in fake_waha.sent_messages[-1]["text"]

    with session_factory() as db:
        media_file = db.scalar(select(MediaFile))
        receipt = db.scalar(select(Receipt))
        job = db.scalar(select(Job))
        assert media_file is not None
        assert media_file.file_type == "receipt"
        assert media_file.source == "whatsapp_receipt"
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


def test_waha_receipt_total_can_be_edited_before_confirmation(
    test_client: tuple[TestClient, sessionmaker[Session], FakeWahaClient, FakeOcrClient],
) -> None:
    client, session_factory, fake_waha, fake_ocr = test_client
    _create_linked_whatsapp_user(session_factory)
    fake_ocr.text = "TOKO SAKOO\nKopi Rp 12.000\nRoti Rp 8.000"

    image_response = client.post("/webhook/waha", json=_waha_image_update())
    assert image_response.status_code == 200, image_response.text
    assert image_response.json()["transaction_status"] == "manual_input_required"
    assert "edit total" in fake_waha.sent_messages[-1]["text"].lower()

    edit_response = client.post("/webhook/waha", json=_waha_text_update("edit total 21000"))
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
        assert receipt is not None
        assert receipt.status == "confirmed"
        assert receipt.transaction_id == transaction.id


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


def _waha_image_update() -> dict[str, Any]:
    return {
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


def _waha_text_update(text: str) -> dict[str, Any]:
    return {
        "event": "message",
        "session": "default",
        "payload": {
            "id": f"msg-{text}",
            "from": "6281234567890@c.us",
            "fromMe": False,
            "body": text,
            "type": "text",
        },
    }
