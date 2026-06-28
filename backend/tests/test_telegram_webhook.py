import os
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
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
    Transaction,
    User,
    UserPlatformAccount,
)
from app.modules.telegram.client import get_telegram_client


class FakeTelegramClient:
    def __init__(self) -> None:
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


@pytest.fixture()
def test_client() -> Iterator[tuple[TestClient, sessionmaker[Session], FakeTelegramClient]]:
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
            ]
        )
        db.commit()

    fake_telegram_client = FakeTelegramClient()

    def override_get_db() -> Iterator[Session]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_telegram_client] = lambda: fake_telegram_client

    with TestClient(app) as client:
        yield client, TestingSessionLocal, fake_telegram_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    get_settings.cache_clear()


def test_telegram_webhook_rejects_invalid_secret(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient],
) -> None:
    client, _session_factory, _fake_telegram = test_client

    response = client.post(
        "/webhook/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        json=_telegram_update(text="beli makan 20 ribu"),
    )

    assert response.status_code == 401


def test_unlinked_telegram_user_gets_linking_instruction(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient],
) -> None:
    client, session_factory, fake_telegram = test_client

    response = _post_telegram_update(client, text="beli makan 20 ribu")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["linking_status"] == "unlinked"
    assert payload["transaction_status"] is None
    assert payload["reply_status"] == "sent"
    assert fake_telegram.sent_messages[0]["chat_id"] == "456"
    assert "hubungkan KODE" in fake_telegram.sent_messages[0]["text"]

    with session_factory() as db:
        assert db.scalar(select(Transaction)) is None
        log = db.scalar(select(BotLog))
        assert log is not None
        assert log.platform == "telegram"
        assert log.status == "received"


def test_valid_linking_code_links_telegram_account(
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient],
) -> None:
    client, session_factory, fake_telegram = test_client
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
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient],
) -> None:
    client, session_factory, fake_telegram = test_client
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
    test_client: tuple[TestClient, sessionmaker[Session], FakeTelegramClient],
) -> None:
    client, session_factory, fake_telegram = test_client
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


def _post_telegram_update(
    client: TestClient,
    *,
    text: str,
) -> Any:
    return client.post(
        "/webhook/telegram",
        headers={"X-Telegram-Bot-Api-Secret-Token": "test-telegram-secret"},
        json=_telegram_update(text=text),
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
