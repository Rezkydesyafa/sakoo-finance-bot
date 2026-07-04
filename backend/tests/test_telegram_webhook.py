import os
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
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
from app.models import (
    AccountLinkingCode,
    BotLog,
    Category,
    Job,
    MediaFile,
    Receipt,
    Transaction,
    User,
    UserPlatformAccount,
)
from app.modules.jobs.service import get_receipt_ocr_enqueue, get_report_pdf_enqueue
from app.modules.telegram.commands import BOT_COMMANDS, register_bot_commands
from app.modules.telegram.client import DownloadedTelegramFile, get_telegram_client


class FakeTelegramClient:
    def __init__(self) -> None:
        self.sent_messages: list[dict[str, Any]] = []
        self.chat_actions: list[dict[str, str]] = []
        self.menu_buttons: list[dict[str, Any]] = []
        self.edited_messages: list[dict[str, Any]] = []
        self.answered_callback_queries: list[dict[str, Any]] = []
        self.commands: list[dict[str, str]] | None = None
        self.downloaded_file_ids: list[str] = []
        self.downloaded_media = DownloadedTelegramFile(
            content=b"fake-telegram-receipt",
            content_type="application/octet-stream",
            filename="telegram-receipt.jpg",
        )

    def send_message(
        self,
        *,
        chat_id: str,
        text: str,
        parse_mode: str | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.sent_messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode or "",
                "reply_markup": reply_markup,
            }
        )
        return {"ok": True, "result": {"message_id": len(self.sent_messages)}}

    def send_chat_action(self, *, chat_id: str, action: str) -> dict[str, Any]:
        self.chat_actions.append({"chat_id": chat_id, "action": action})
        return {"ok": True, "result": True}

    def set_chat_menu_button(self, *, chat_id: str, text: str, url: str) -> dict[str, Any]:
        self.menu_buttons.append({"chat_id": chat_id, "text": text, "url": url})
        return {"ok": True, "result": True}

    def edit_message_text(
        self,
        *,
        chat_id: str,
        message_id: int,
        text: str,
        parse_mode: str | None = None,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.edited_messages.append(
            {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "parse_mode": parse_mode or "",
                "reply_markup": reply_markup,
            }
        )
        return {"ok": True, "result": {"message_id": message_id}}

    def answer_callback_query(
        self,
        *,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> dict[str, Any]:
        self.answered_callback_queries.append(
            {
                "callback_query_id": callback_query_id,
                "text": text,
                "show_alert": show_alert,
            }
        )
        return {"ok": True, "result": True}

    def set_my_commands(self, commands: list[dict[str, str]]) -> dict[str, Any]:
        self.commands = commands
        return {"ok": True, "result": True}

    def download_media(
        self,
        *,
        file_id: str,
        fallback_filename: str | None = None,
        fallback_content_type: str | None = None,
    ) -> DownloadedTelegramFile:
        self.downloaded_file_ids.append(file_id)
        return self.downloaded_media


@pytest.fixture()
def test_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[
    tuple[
        TestClient,
        sessionmaker[Session],
        FakeTelegramClient,
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
                Category(name="Makanan", type="expense"),
                Category(name="Gaji", type="income"),
                Category(name="Lainnya", type="expense"),
                Category(name="Uang Saku", type="income"),
            ]
        )
        db.commit()

    fake_telegram_client = FakeTelegramClient()
    queued_receipt_jobs: list[dict[str, Any]] = []

    def override_get_db() -> Iterator[Session]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def fake_receipt_enqueue(**kwargs: Any) -> None:
        queued_receipt_jobs.append(kwargs)

    def fake_report_pdf_enqueue(**kwargs: Any) -> None:
        return None

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_telegram_client] = lambda: fake_telegram_client
    app.dependency_overrides[get_receipt_ocr_enqueue] = lambda: fake_receipt_enqueue
    app.dependency_overrides[get_report_pdf_enqueue] = lambda: fake_report_pdf_enqueue

    with TestClient(app) as client:
        yield client, TestingSessionLocal, fake_telegram_client, queued_receipt_jobs

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    get_settings.cache_clear()


def test_telegram_webhook_rejects_invalid_secret(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient, list[dict[str, Any]]],
) -> None:
    client, _session_factory, _fake_telegram, _queued_jobs = test_client

    response = client.post(
        "/webhook/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        json=_telegram_update(text="beli makan 20 ribu"),
    )

    assert response.status_code == 401


def test_unlinked_telegram_user_gets_linking_instruction(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient, list[dict[str, Any]]],
) -> None:
    client, session_factory, fake_telegram, _queued_jobs = test_client

    response = _post_telegram_update(client, text="beli makan 20 ribu")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["linking_status"] == "unlinked"
    assert payload["transaction_status"] is None
    assert payload["reply_status"] == "sent"
    assert fake_telegram.sent_messages[0]["chat_id"] == "456"
    assert "Silakan daftar atau login" in fake_telegram.sent_messages[0]["text"]
    assert "hubungkan KODE" in fake_telegram.sent_messages[0]["text"]
    assert _keyboard_contains_url(fake_telegram.sent_messages[0]["reply_markup"], "/register")
    assert _keyboard_contains_web_app(
        fake_telegram.sent_messages[0]["reply_markup"],
        "https://sakoo.lab-sigma.web.id",
    )
    assert fake_telegram.menu_buttons[-1] == {
        "chat_id": "456",
        "text": "Sakoo",
        "url": "https://sakoo.lab-sigma.web.id",
    }

    with session_factory() as db:
        assert db.scalar(select(Transaction)) is None
        log = db.scalar(select(BotLog))
        assert log is not None
        assert log.platform == "telegram"
        assert log.status == "received"


def test_register_bot_commands_uses_telegram_set_my_commands() -> None:
    fake_telegram = FakeTelegramClient()

    result = register_bot_commands(fake_telegram)  # type: ignore[arg-type]

    assert result["ok"] is True
    assert fake_telegram.commands == BOT_COMMANDS
    assert fake_telegram.commands[0] == {
        "command": "start",
        "description": "Mulai Sakoo",
    }


def test_start_command_shows_main_menu_without_linking(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient, list[dict[str, Any]]],
) -> None:
    client, _session_factory, fake_telegram, _queued_jobs = test_client

    response = _post_telegram_update(client, text="/start")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["message_type"] == "command"
    assert payload["linking_status"] == "unlinked"
    assert payload["transaction_status"] == "start"
    assert payload["reply_status"] == "sent"
    assert "Sakoo Finance Bot" in fake_telegram.sent_messages[0]["text"]
    assert _keyboard_contains(fake_telegram.sent_messages[0]["reply_markup"], "MENU_BALANCE")
    assert _keyboard_contains(fake_telegram.sent_messages[0]["reply_markup"], "MENU_ADD")
    assert _keyboard_contains_web_app(
        fake_telegram.sent_messages[0]["reply_markup"],
        "https://sakoo.lab-sigma.web.id",
    )
    assert fake_telegram.menu_buttons[-1]["url"] == "https://sakoo.lab-sigma.web.id"


def test_add_menu_callback_edits_message_without_transaction_parser(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient, list[dict[str, Any]]],
) -> None:
    client, session_factory, fake_telegram, _queued_jobs = test_client

    response = _post_telegram_callback(client, data="MENU_ADD")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["message_type"] == "callback_query"
    assert payload["transaction_status"] == "add_menu"
    assert payload["reply_status"] == "sent"
    assert fake_telegram.answered_callback_queries[0]["callback_query_id"] == "callback-1"
    assert "Mau catat transaksi" in fake_telegram.edited_messages[0]["text"]
    assert _keyboard_contains(fake_telegram.edited_messages[0]["reply_markup"], "ADD_EXPENSE")

    with session_factory() as db:
        assert db.scalar(select(Transaction)) is None


def test_balance_callback_for_linked_user_uses_menu_handler(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient, list[dict[str, Any]]],
) -> None:
    client, session_factory, fake_telegram, _queued_jobs = test_client
    with session_factory() as db:
        user = _create_user(db)
        _link_telegram_user(db, user.id)
        income_category = db.scalar(select(Category).where(Category.name == "Gaji"))
        expense_category = db.scalar(select(Category).where(Category.name == "Makanan"))
        db.add_all(
            [
                Transaction(
                    user_id=user.id,
                    type="income",
                    amount=Decimal("100000.00"),
                    category_id=income_category.id if income_category else None,
                    description="gaji",
                    transaction_date=datetime.now(timezone.utc).date(),
                    source="telegram_text",
                ),
                Transaction(
                    user_id=user.id,
                    type="expense",
                    amount=Decimal("20000.00"),
                    category_id=expense_category.id if expense_category else None,
                    description="makan",
                    transaction_date=datetime.now(timezone.utc).date(),
                    source="telegram_text",
                ),
            ]
        )
        db.commit()

    response = _post_telegram_callback(client, data="MENU_BALANCE")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["transaction_status"] == "balance"
    assert "Sisa saldo: Rp80.000" in fake_telegram.edited_messages[0]["text"]
    assert fake_telegram.answered_callback_queries


def test_linked_telegram_slash_commands_use_menu_handlers(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient, list[dict[str, Any]]],
) -> None:
    client, session_factory, fake_telegram, _queued_jobs = test_client
    with session_factory() as db:
        user = _create_user(db)
        _link_telegram_user(db, user.id)
        income_category = db.scalar(select(Category).where(Category.name == "Gaji"))
        expense_category = db.scalar(select(Category).where(Category.name == "Makanan"))
        db.add_all(
            [
                Transaction(
                    user_id=user.id,
                    type="income",
                    amount=Decimal("100000.00"),
                    category_id=income_category.id if income_category else None,
                    description="gaji",
                    transaction_date=datetime.now(timezone.utc).date(),
                    source="telegram_text",
                ),
                Transaction(
                    user_id=user.id,
                    type="expense",
                    amount=Decimal("20000.00"),
                    category_id=expense_category.id if expense_category else None,
                    description="makan",
                    transaction_date=datetime.now(timezone.utc).date(),
                    source="telegram_text",
                ),
            ]
        )
        db.commit()

    command_expectations = [
        ("/saldo", "balance", "Sisa saldo: Rp80.000"),
        ("/pengeluaran", "expense_list", "List pengeluaran"),
        ("/pemasukan", "income_list", "List pemasukan"),
        ("/laporan", "report", "Laporan bulan ini"),
        ("/riwayat", "history", "Riwayat transaksi terbaru"),
    ]
    for index, (command, status, expected_text) in enumerate(command_expectations, start=1):
        response = _post_telegram_update(
            client,
            text=command,
            update_id=1100 + index,
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["message_type"] == "command"
        assert payload["transaction_status"] == status
        assert payload["reply_status"] == "sent"
        assert expected_text in fake_telegram.sent_messages[-1]["text"]
        assert _keyboard_contains(fake_telegram.sent_messages[-1]["reply_markup"], "MENU_BALANCE")


def test_linked_telegram_export_command_queues_monthly_pdf(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient, list[dict[str, Any]]],
) -> None:
    client, session_factory, fake_telegram, _queued_jobs = test_client
    with session_factory() as db:
        user = _create_user(db)
        _link_telegram_user(db, user.id)
        db.commit()

    response = _post_telegram_update(client, text="/export", update_id=1110)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["message_type"] == "command"
    assert payload["transaction_status"] == "queued"
    assert payload["job_id"] is not None
    assert "export PDF laporan bulan ini" in fake_telegram.sent_messages[-1]["text"]
    with session_factory() as db:
        job = db.scalar(select(Job))
        assert job is not None
        assert job.job_type == "report_pdf"
        assert job.status == "queued"


def test_add_expense_callback_sets_state_and_next_text_saves_expense(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient, list[dict[str, Any]]],
) -> None:
    client, session_factory, fake_telegram, _queued_jobs = test_client
    with session_factory() as db:
        user = _create_user(db)
        _link_telegram_user(db, user.id)
        db.commit()

    callback_response = _post_telegram_callback(client, data="ADD_EXPENSE")

    assert callback_response.status_code == 200, callback_response.text
    assert callback_response.json()["transaction_status"] == "WAITING_EXPENSE_INPUT"
    assert "Mode catat pengeluaran aktif" in fake_telegram.edited_messages[0]["text"]

    text_response = _post_telegram_update(client, text="makan 20 ribu", update_id=1002)

    assert text_response.status_code == 200, text_response.text
    payload = text_response.json()
    assert payload["transaction_status"] == "saved"
    with session_factory() as db:
        transaction = db.scalar(select(Transaction))
        assert transaction is not None
        assert transaction.type == "expense"
        assert transaction.amount == Decimal("20000.00")


def test_add_income_callback_forces_next_text_as_income(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient, list[dict[str, Any]]],
) -> None:
    client, session_factory, _fake_telegram, _queued_jobs = test_client
    with session_factory() as db:
        user = _create_user(db)
        _link_telegram_user(db, user.id)
        db.commit()

    callback_response = _post_telegram_callback(client, data="ADD_INCOME")

    assert callback_response.status_code == 200, callback_response.text
    assert callback_response.json()["transaction_status"] == "WAITING_INCOME_INPUT"

    text_response = _post_telegram_update(client, text="makan 20 ribu", update_id=1003)

    assert text_response.status_code == 200, text_response.text
    payload = text_response.json()
    assert payload["transaction_status"] == "saved"
    with session_factory() as db:
        transaction = db.scalar(select(Transaction))
        assert transaction is not None
        assert transaction.type == "income"


def test_valid_linking_code_links_telegram_account(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient, list[dict[str, Any]]],
) -> None:
    client, session_factory, fake_telegram, _queued_jobs = test_client
    with session_factory() as db:
        user = _create_user(db)
        db.add(
            AccountLinkingCode(
                user_id=user.id,
                code="ABC123",
                expired_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            )
        )
        db.commit()

    response = _post_telegram_update(client, text="hubungkan ABC123")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["linking_status"] == "success"
    assert payload["user_id"] is not None
    assert payload["reply_status"] == "sent"
    assert "berhasil terhubung" in fake_telegram.sent_messages[0]["text"]

    with session_factory() as db:
        account = db.scalar(select(UserPlatformAccount))
        assert account is not None
        assert account.platform == "telegram"
        assert account.platform_user_id == "123"
        assert account.chat_id == "456"
        linking_code = db.scalar(select(AccountLinkingCode))
        assert linking_code is not None
        assert linking_code.used_at is not None


def test_linked_telegram_user_can_save_text_transaction(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient, list[dict[str, Any]]],
) -> None:
    client, session_factory, fake_telegram, _queued_jobs = test_client
    with session_factory() as db:
        user = _create_user(db)
        _link_telegram_user(db, user.id)
        db.commit()

    response = _post_telegram_update(client, text="beli makan 20 ribu")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["linking_status"] == "linked"
    assert payload["transaction_status"] == "saved"
    assert payload["transaction_id"] is not None
    assert payload["reply_status"] == "sent"
    assert "Tercatat" in fake_telegram.sent_messages[0]["text"]

    with session_factory() as db:
        transaction = db.scalar(select(Transaction))
        assert transaction is not None
        assert transaction.source == "telegram_text"
        assert transaction.type == "expense"
        assert transaction.amount == Decimal("20000.00")
        assert transaction.description == "beli makan"


def test_missing_amount_asks_telegram_user_to_clarify(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient, list[dict[str, Any]]],
) -> None:
    client, session_factory, fake_telegram, _queued_jobs = test_client
    with session_factory() as db:
        user = _create_user(db)
        _link_telegram_user(db, user.id)
        db.commit()

    response = _post_telegram_update(client, text="beli makan")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["transaction_status"] == "needs_confirmation"
    assert payload["transaction_id"] is None
    assert payload["reply_status"] == "sent"
    assert "nominal belum terbaca" in fake_telegram.sent_messages[0]["text"]

    with session_factory() as db:
        assert db.scalar(select(Transaction)) is None


def test_linked_telegram_user_photo_receipt_is_queued_for_ocr(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient, list[dict[str, Any]]],
) -> None:
    client, session_factory, fake_telegram, queued_jobs = test_client
    with session_factory() as db:
        user = _create_user(db)
        _link_telegram_user(db, user.id)
        db.commit()

    response = client.post(
        "/webhook/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-telegram-secret"},
        json=_telegram_photo_update(caption="Struk makan siang"),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["message_type"] == "receipt_ocr"
    assert payload["transaction_status"] == "queued"
    assert payload["job_id"] is not None
    assert payload["reply_status"] == "sent"
    assert fake_telegram.downloaded_file_ids == ["telegram-photo-large"]
    assert "masuk antrean OCR" in fake_telegram.sent_messages[-1]["text"]
    assert len(queued_jobs) == 1
    assert queued_jobs[0]["source"] == "telegram"
    assert queued_jobs[0]["notify_chat_id"] == "456"
    assert queued_jobs[0]["notify_platform"] == "telegram"

    with session_factory() as db:
        media_file = db.scalar(select(MediaFile))
        receipt = db.scalar(select(Receipt))
        job = db.scalar(select(Job))
        assert media_file is not None
        assert media_file.file_type == "receipt"
        assert media_file.mime_type == "image/jpeg"
        assert media_file.source == "telegram_receipt"
        assert receipt is not None
        assert receipt.caption_text == "Struk makan siang"
        assert job is not None
        assert job.status == "queued"


def test_telegram_photo_without_caption_asks_for_receipt_context(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient, list[dict[str, Any]]],
) -> None:
    client, session_factory, fake_telegram, _queued_jobs = test_client
    with session_factory() as db:
        user = _create_user(db)
        _link_telegram_user(db, user.id)
        db.commit()

    photo_response = client.post(
        "/webhook/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-telegram-secret"},
        json=_telegram_photo_update(update_id=3101),
    )

    assert photo_response.status_code == 200, photo_response.text
    assert photo_response.json()["transaction_status"] == "queued"
    assert "balas keterangan struknya" in fake_telegram.sent_messages[-1]["text"]

    caption_response = _post_telegram_update(
        client,
        text="makan siang",
        update_id=3102,
    )

    assert caption_response.status_code == 200, caption_response.text
    payload = caption_response.json()
    assert payload["message_type"] == "receipt_ocr"
    assert payload["transaction_status"] == "caption_saved"
    assert "keterangan struk kusimpan" in fake_telegram.sent_messages[-1]["text"]

    with session_factory() as db:
        receipt = db.scalar(select(Receipt))
        assert receipt is not None
        assert receipt.caption_text == "makan siang"
        assert db.scalar(select(Transaction)) is None


def test_telegram_receipt_confirmation_saves_pending_receipt(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient, list[dict[str, Any]]],
) -> None:
    client, session_factory, fake_telegram, _queued_jobs = test_client
    with session_factory() as db:
        user = _create_user(db)
        _link_telegram_user(db, user.id)
        _create_pending_receipt(db, user.id, total=Decimal("15415.00"))
        db.commit()

    response = _post_telegram_update(client, text="YA", update_id=3201)

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["message_type"] == "receipt_ocr"
    assert payload["transaction_status"] == "saved"
    assert payload["transaction_id"] is not None
    assert "Transaksi struk tersimpan" in fake_telegram.sent_messages[-1]["text"]

    with session_factory() as db:
        receipt = db.scalar(select(Receipt))
        transaction = db.scalar(select(Transaction))
        assert receipt is not None
        assert receipt.status == "confirmed"
        assert transaction is not None
        assert transaction.amount == Decimal("15415.00")


def test_telegram_receipt_total_can_be_corrected_with_plain_amount(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient, list[dict[str, Any]]],
) -> None:
    client, session_factory, fake_telegram, _queued_jobs = test_client
    with session_factory() as db:
        user = _create_user(db)
        _link_telegram_user(db, user.id)
        _create_pending_receipt(db, user.id, total=Decimal("15415.00"))
        db.commit()

    edit_response = _post_telegram_update(client, text="20000", update_id=3301)
    confirm_response = _post_telegram_update(client, text="ya", update_id=3302)

    assert edit_response.status_code == 200, edit_response.text
    assert edit_response.json()["transaction_status"] == "edit_updated"
    assert "Rp20.000" in fake_telegram.sent_messages[-1]["text"]
    assert confirm_response.status_code == 200, confirm_response.text
    assert confirm_response.json()["transaction_status"] == "saved"

    with session_factory() as db:
        transaction = db.scalar(select(Transaction))
        assert transaction is not None
        assert transaction.amount == Decimal("20000.00")


def _post_telegram_update(
    client: TestClient,
    *,
    text: str,
    update_id: int = 1001,
) -> Any:
    return client.post(
        "/webhook/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-telegram-secret"},
        json=_telegram_update(text=text, update_id=update_id),
    )


def _post_telegram_callback(
    client: TestClient,
    *,
    data: str,
    update_id: int = 2001,
) -> Any:
    return client.post(
        "/webhook/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-telegram-secret"},
        json=_telegram_callback_update(data=data, update_id=update_id),
    )


def _telegram_update(
    *,
    text: str,
    update_id: int = 1001,
) -> dict[str, Any]:
    return {
        "update_id": update_id,
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
            "text": text,
        },
    }


def _telegram_callback_update(
    *,
    data: str,
    update_id: int,
) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "callback_query": {
            "id": "callback-1",
            "from": {
                "id": 123,
                "is_bot": False,
                "first_name": "Tester",
                "username": "tester",
            },
            "message": {
                "message_id": 99,
                "chat": {
                    "id": 456,
                    "first_name": "Tester",
                    "username": "tester",
                    "type": "private",
                },
                "date": 1760000000,
                "text": "Menu Sakoo",
            },
            "chat_instance": "chat-instance",
            "data": data,
        },
    }


def _telegram_photo_update(
    *,
    caption: str | None = None,
    update_id: int = 3001,
) -> dict[str, Any]:
    message: dict[str, Any] = {
        "message_id": 11,
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
        "photo": [
            {
                "file_id": "telegram-photo-small",
                "file_unique_id": "small",
                "width": 90,
                "height": 90,
                "file_size": 1200,
            },
            {
                "file_id": "telegram-photo-large",
                "file_unique_id": "large",
                "width": 900,
                "height": 1200,
                "file_size": 120000,
            },
        ],
    }
    if caption is not None:
        message["caption"] = caption
    return {"update_id": update_id, "message": message}


def _keyboard_contains(reply_markup: dict[str, Any] | None, callback_data: str) -> bool:
    if not reply_markup:
        return False
    return any(
        button.get("callback_data") == callback_data
        for row in reply_markup.get("inline_keyboard", [])
        for button in row
    )


def _keyboard_contains_url(reply_markup: dict[str, Any] | None, url_part: str) -> bool:
    if not reply_markup:
        return False
    return any(
        url_part in button.get("url", "")
        for row in reply_markup.get("inline_keyboard", [])
        for button in row
    )


def _keyboard_contains_web_app(reply_markup: dict[str, Any] | None, url: str) -> bool:
    if not reply_markup:
        return False
    return any(
        button.get("web_app", {}).get("url") == url
        for row in reply_markup.get("inline_keyboard", [])
        for button in row
    )


def _create_user(db: Session) -> User:
    user = User(
        name="Telegram User",
        email="telegram@example.com",
        password_hash="hashed-password",
    )
    db.add(user)
    db.flush()
    return user


def _link_telegram_user(db: Session, user_id: int) -> None:
    db.add(
        UserPlatformAccount(
            user_id=user_id,
            platform="telegram",
            platform_user_id="123",
            chat_id="456",
        )
    )


def _create_pending_receipt(
    db: Session,
    user_id: int,
    *,
    total: Decimal,
) -> Receipt:
    media_file = MediaFile(
        user_id=user_id,
        file_type="receipt",
        original_filename="receipt.jpg",
        stored_path="receipts/test.jpg",
        mime_type="image/jpeg",
        size=10,
        source="telegram_receipt",
    )
    db.add(media_file)
    db.flush()
    receipt = Receipt(
        user_id=user_id,
        media_file_id=media_file.id,
        merchant_name="WARUNG AI",
        receipt_date=datetime.now(timezone.utc).date(),
        total_amount=total,
        confidence=Decimal("1.0000"),
        status="processed",
    )
    db.add(receipt)
    return receipt
