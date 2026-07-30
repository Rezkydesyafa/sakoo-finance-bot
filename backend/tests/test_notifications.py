from collections.abc import Iterator
from datetime import date, datetime, time, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import (
    BotLog,
    Category,
    CategoryBudget,
    Transaction,
    User,
    UserPlatformAccount,
    UserPreference,
)
from app.modules.notifications.service import (
    check_budget_notification,
    dispatch_due_notifications,
)


@pytest.fixture()
def test_client() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    get_settings.cache_clear()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
    Base.metadata.create_all(bind=engine)
    with session_factory() as db:
        db.add_all(
            [
                Category(name="Makanan", type="expense"),
                Category(name="Transportasi", type="expense"),
                Category(name="Gaji", type="income"),
            ]
        )
        db.commit()

    def override_get_db() -> Iterator[Session]:
        with session_factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, session_factory
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


class FakeTelegramClient:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send_message(self, *, chat_id: str, text: str, **_kwargs) -> dict:
        self.messages.append((chat_id, text))
        return {"ok": True}


class FakeWahaClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.messages: list[tuple[str, str]] = []
        self.fail = fail

    def send_text(self, *, chat_id: str, text: str, **_kwargs) -> dict:
        if self.fail:
            raise RuntimeError("waha unavailable")
        self.messages.append((chat_id, text))
        return {"ok": True}


def test_notification_preferences_api_defaults_updates_and_lists_channels(test_client) -> None:
    client, session_factory = test_client
    token = _register_and_login(client, "notify-api@example.com")
    user_id = _user_id(session_factory, "notify-api@example.com")
    with session_factory() as db:
        db.add(
            UserPlatformAccount(
                user_id=user_id,
                platform="telegram",
                platform_user_id="tg-api",
                chat_id="chat-api",
                is_active=True,
            )
        )
        db.commit()

    response = client.get("/api/notifications/preferences", headers=_auth_headers(token))
    assert response.status_code == 200, response.text
    assert response.json() == {
        "daily_reminder_enabled": False,
        "daily_reminder_time": "20:00",
        "weekly_summary_enabled": False,
        "monthly_summary_enabled": False,
        "budget_alert_enabled": True,
        "timezone": "Asia/Jakarta",
        "active_channels": ["telegram"],
    }

    payload = {
        "daily_reminder_enabled": True,
        "daily_reminder_time": "21:15",
        "weekly_summary_enabled": True,
        "monthly_summary_enabled": True,
        "budget_alert_enabled": False,
        "timezone": "Asia/Jayapura",
    }
    updated = client.put(
        "/api/notifications/preferences",
        headers=_auth_headers(token),
        json=payload,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json() == {**payload, "active_channels": ["telegram"]}
    assert client.put(
        "/api/notifications/preferences",
        headers=_auth_headers(token),
        json={**payload, "daily_reminder_time": "25:00"},
    ).status_code == 422
    assert client.get("/api/notifications/preferences").status_code == 401


@pytest.mark.parametrize(
    ("timezone_name", "due_utc_hour"),
    [
        ("Asia/Jakarta", 13),
        ("Asia/Makassar", 12),
        ("Asia/Jayapura", 11),
    ],
)
def test_daily_dispatch_uses_timezone_all_channels_and_is_idempotent(
    test_client,
    timezone_name: str,
    due_utc_hour: int,
) -> None:
    _client, session_factory = test_client
    user_id = _create_user(session_factory, "daily@example.com")
    telegram = FakeTelegramClient()
    waha = FakeWahaClient()
    with session_factory() as db:
        db.add(
            UserPreference(
                user_id=user_id,
                reply_style="friendly",
                daily_reminder_enabled=True,
                daily_reminder_time=time(20, 0),
                timezone=timezone_name,
            )
        )
        db.add_all(
            [
                UserPlatformAccount(
                    user_id=user_id,
                    platform="telegram",
                    platform_user_id="tg-daily",
                    chat_id="tg-chat",
                ),
                UserPlatformAccount(
                    user_id=user_id,
                    platform="whatsapp",
                    platform_user_id="wa-daily",
                    chat_id="wa-chat",
                ),
            ]
        )
        db.commit()
        before = dispatch_due_notifications(
            db,
            now_utc=datetime(2026, 7, 13, due_utc_hour - 1, 59, tzinfo=timezone.utc),
            telegram_client=telegram,
            waha_client=waha,
        )
        first = dispatch_due_notifications(
            db,
            now_utc=datetime(2026, 7, 13, due_utc_hour, 0, tzinfo=timezone.utc),
            telegram_client=telegram,
            waha_client=waha,
        )
        second = dispatch_due_notifications(
            db,
            now_utc=datetime(2026, 7, 13, due_utc_hour + 1, 0, tzinfo=timezone.utc),
            telegram_client=telegram,
            waha_client=waha,
        )

    assert before == {"sent": 0, "failed": 0, "skipped": 0}
    assert first["sent"] == 2
    assert second["skipped"] == 2
    assert len(telegram.messages) == len(waha.messages) == 1
    assert "makan 25rb" in telegram.messages[0][1]


def test_weekly_monthly_summary_and_channel_failure_are_isolated(test_client) -> None:
    _client, session_factory = test_client
    user_id = _create_user(session_factory, "summary@example.com")
    telegram = FakeTelegramClient()
    waha = FakeWahaClient(fail=True)
    with session_factory() as db:
        category = db.scalar(select(Category).where(Category.name == "Makanan"))
        assert category is not None
        db.add(
            UserPreference(
                user_id=user_id,
                weekly_summary_enabled=True,
                monthly_summary_enabled=True,
                timezone="Asia/Jakarta",
            )
        )
        db.add_all(
            [
                UserPlatformAccount(
                    user_id=user_id,
                    platform="telegram",
                    platform_user_id="tg-summary",
                    chat_id="tg-summary-chat",
                ),
                UserPlatformAccount(
                    user_id=user_id,
                    platform="whatsapp",
                    platform_user_id="wa-summary",
                    chat_id="wa-summary-chat",
                ),
                Transaction(
                    user_id=user_id,
                    type="expense",
                    amount=Decimal("125000"),
                    category_id=category.id,
                    description="makan akhir bulan",
                    transaction_date=date(2026, 5, 30),
                    source="dashboard_manual",
                    status="confirmed",
                ),
            ]
        )
        db.commit()
        result = dispatch_due_notifications(
            db,
            now_utc=datetime(2026, 6, 1, 1, 0, tzinfo=timezone.utc),
            telegram_client=telegram,
            waha_client=waha,
        )
        failed = list(db.scalars(select(BotLog).where(BotLog.status == "failed")))

    assert result["sent"] == 2
    assert result["failed"] == 2
    assert len(telegram.messages) == 2
    assert len(failed) == 2


def test_budget_alerts_at_80_and_100_once_per_channel(test_client) -> None:
    _client, session_factory = test_client
    user_id = _create_user(session_factory, "budget-notify@example.com")
    telegram = FakeTelegramClient()
    waha = FakeWahaClient()
    with session_factory() as db:
        category = db.scalar(select(Category).where(Category.name == "Makanan"))
        assert category is not None
        db.add(CategoryBudget(user_id=user_id, category_id=category.id, monthly_limit=Decimal("1000")))
        db.add_all(
            [
                UserPlatformAccount(
                    user_id=user_id,
                    platform="telegram",
                    platform_user_id="tg-budget-notify",
                    chat_id="tg-budget-chat",
                ),
                UserPlatformAccount(
                    user_id=user_id,
                    platform="whatsapp",
                    platform_user_id="wa-budget-notify",
                    chat_id="wa-budget-chat",
                ),
            ]
        )
        first_transaction = Transaction(
            user_id=user_id,
            type="expense",
            amount=Decimal("800"),
            category_id=category.id,
            description="budget 80",
            transaction_date=date(2026, 7, 13),
            source="dashboard_manual",
            status="confirmed",
        )
        db.add(first_transaction)
        db.commit()
        first = check_budget_notification(
            db,
            transaction_id=first_transaction.id,
            now_utc=datetime(2026, 7, 13, 12, tzinfo=timezone.utc),
            telegram_client=telegram,
            waha_client=waha,
        )
        duplicate = check_budget_notification(
            db,
            transaction_id=first_transaction.id,
            now_utc=datetime(2026, 7, 13, 12, tzinfo=timezone.utc),
            telegram_client=telegram,
            waha_client=waha,
        )
        second_transaction = Transaction(
            user_id=user_id,
            type="expense",
            amount=Decimal("200"),
            category_id=category.id,
            description="budget 100",
            transaction_date=date(2026, 7, 13),
            source="dashboard_manual",
            status="confirmed",
        )
        db.add(second_transaction)
        db.commit()
        second = check_budget_notification(
            db,
            transaction_id=second_transaction.id,
            now_utc=datetime(2026, 7, 13, 12, tzinfo=timezone.utc),
            telegram_client=telegram,
            waha_client=waha,
        )

    assert first["sent"] == 2
    assert duplicate["skipped"] == 2
    assert second["sent"] == 2
    assert len(telegram.messages) == len(waha.messages) == 2
    assert "sekitar" in telegram.messages[0][1]
    assert "melewati batas" in telegram.messages[1][1]


def test_budget_alert_ignores_below_threshold_disabled_and_backdated(test_client) -> None:
    _client, session_factory = test_client
    user_id = _create_user(session_factory, "budget-ignore@example.com")
    telegram = FakeTelegramClient()
    with session_factory() as db:
        category = db.scalar(select(Category).where(Category.name == "Makanan"))
        assert category is not None
        db.add(CategoryBudget(user_id=user_id, category_id=category.id, monthly_limit=Decimal("1000")))
        db.add(
            UserPlatformAccount(
                user_id=user_id,
                platform="telegram",
                platform_user_id="tg-budget-ignore",
                chat_id="tg-budget-ignore-chat",
            )
        )
        below = Transaction(
            user_id=user_id,
            type="expense",
            amount=Decimal("790"),
            category_id=category.id,
            transaction_date=date(2026, 7, 13),
            source="dashboard_manual",
            status="confirmed",
        )
        db.add(below)
        db.commit()
        assert check_budget_notification(
            db,
            transaction_id=below.id,
            now_utc=datetime(2026, 7, 13, 12, tzinfo=timezone.utc),
            telegram_client=telegram,
        )["sent"] == 0

        preference = UserPreference(user_id=user_id, budget_alert_enabled=False)
        db.add(preference)
        disabled = Transaction(
            user_id=user_id,
            type="expense",
            amount=Decimal("410"),
            category_id=category.id,
            transaction_date=date(2026, 7, 13),
            source="dashboard_manual",
            status="confirmed",
        )
        db.add(disabled)
        db.commit()
        assert check_budget_notification(
            db,
            transaction_id=disabled.id,
            now_utc=datetime(2026, 7, 13, 12, tzinfo=timezone.utc),
            telegram_client=telegram,
        )["sent"] == 0

        preference.budget_alert_enabled = True
        backdated = Transaction(
            user_id=user_id,
            type="expense",
            amount=Decimal("1000"),
            category_id=category.id,
            transaction_date=date(2026, 6, 30),
            source="dashboard_manual",
            status="confirmed",
        )
        db.add(backdated)
        db.commit()
        assert check_budget_notification(
            db,
            transaction_id=backdated.id,
            now_utc=datetime(2026, 7, 13, 12, tzinfo=timezone.utc),
            telegram_client=telegram,
        )["sent"] == 0
    assert telegram.messages == []


def _register_and_login(client, email: str) -> str:
    password = "super-secret-password"
    assert client.post(
        "/api/auth/register",
        json={"name": "Notify User", "email": email, "password": password},
    ).status_code == 201
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def _create_user(session_factory: sessionmaker[Session], email: str) -> int:
    from app.modules.auth.security import hash_password

    with session_factory() as db:
        user = User(name="Raka Pengguna", email=email, password_hash=hash_password("secret-password"))
        db.add(user)
        db.commit()
        return user.id


def _user_id(session_factory: sessionmaker[Session], email: str) -> int:
    with session_factory() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        return user.id


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
