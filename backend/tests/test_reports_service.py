import os
from collections.abc import Iterator
from datetime import date
from decimal import Decimal

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
from app.models import Category, Transaction, User


@pytest.fixture()
def test_client() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
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
                Category(name="Transportasi", type="expense"),
                Category(name="Gaji", type="income"),
            ]
        )
        db.commit()

    def override_get_db() -> Iterator[Session]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, TestingSessionLocal

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    get_settings.cache_clear()


def test_report_summary_month_matches_database_and_transaction_list(
    test_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = test_client
    token = _register_and_login(client, "owner@example.com")
    other_token = _register_and_login(client, "other@example.com")
    category_ids = _category_ids(session_factory)
    owner_id = _user_id(session_factory, "owner@example.com")
    other_id = _user_id(session_factory, "other@example.com")

    _create_transaction(
        session_factory,
        user_id=owner_id,
        type="income",
        amount="5000000",
        category_id=category_ids["Gaji"],
        description="gaji juni",
        transaction_date=date(2026, 6, 1),
    )
    _create_transaction(
        session_factory,
        user_id=owner_id,
        type="expense",
        amount="20000",
        category_id=category_ids["Makanan"],
        description="makan",
        transaction_date=date(2026, 6, 10),
    )
    _create_transaction(
        session_factory,
        user_id=owner_id,
        type="expense",
        amount="30000",
        category_id=category_ids["Transportasi"],
        description="bensin",
        transaction_date=date(2026, 6, 11),
    )
    _create_transaction(
        session_factory,
        user_id=owner_id,
        type="expense",
        amount="75000",
        category_id=category_ids["Makanan"],
        description="mei ignored",
        transaction_date=date(2026, 5, 31),
    )
    _create_transaction(
        session_factory,
        user_id=other_id,
        type="income",
        amount="999999",
        category_id=category_ids["Gaji"],
        description="other ignored",
        transaction_date=date(2026, 6, 10),
    )

    response = client.get(
        "/api/reports/summary",
        headers=_auth_headers(token),
        params={"period": "month", "date": "2026-06-15", "limit": 2},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["report_type"] == "month"
    assert payload["period_start"] == "2026-06-01"
    assert payload["period_end"] == "2026-06-30"
    assert Decimal(str(payload["total_income"])) == Decimal("5000000.00")
    assert Decimal(str(payload["total_expense"])) == Decimal("50000.00")
    assert Decimal(str(payload["net_balance"])) == Decimal("4950000.00")
    assert payload["transaction_count"] == 3
    assert payload["income_count"] == 1
    assert payload["expense_count"] == 2
    assert payload["total_transactions"] == 3
    assert payload["limit"] == 2
    assert payload["offset"] == 0
    assert payload["has_next"] is True
    assert [item["description"] for item in payload["transactions"]] == [
        "bensin",
        "makan",
    ]

    other_response = client.get(
        "/api/reports/summary",
        headers=_auth_headers(other_token),
        params={"period": "month", "date": "2026-06-15"},
    )
    assert other_response.status_code == 200
    assert Decimal(str(other_response.json()["total_income"])) == Decimal("999999.00")


def test_report_summary_custom_period_works(
    test_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = test_client
    token = _register_and_login(client, "owner@example.com")
    category_ids = _category_ids(session_factory)
    user_id = _user_id(session_factory, "owner@example.com")

    _create_transaction(
        session_factory,
        user_id=user_id,
        type="expense",
        amount="10000",
        category_id=category_ids["Makanan"],
        description="outside",
        transaction_date=date(2026, 6, 9),
    )
    _create_transaction(
        session_factory,
        user_id=user_id,
        type="expense",
        amount="20000",
        category_id=category_ids["Makanan"],
        description="inside",
        transaction_date=date(2026, 6, 10),
    )
    _create_transaction(
        session_factory,
        user_id=user_id,
        type="income",
        amount="100000",
        category_id=category_ids["Gaji"],
        description="inside income",
        transaction_date=date(2026, 6, 12),
    )

    response = client.get(
        "/api/reports/summary",
        headers=_auth_headers(token),
        params={
            "period": "custom",
            "start_date": "2026-06-10",
            "end_date": "2026-06-12",
        },
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["report_type"] == "custom"
    assert payload["period_start"] == "2026-06-10"
    assert payload["period_end"] == "2026-06-12"
    assert Decimal(str(payload["total_income"])) == Decimal("100000.00")
    assert Decimal(str(payload["total_expense"])) == Decimal("20000.00")
    assert payload["transaction_count"] == 2

    missing_range = client.get(
        "/api/reports/summary",
        headers=_auth_headers(token),
        params={"period": "custom"},
    )
    assert missing_range.status_code == 400

    invalid_range = client.get(
        "/api/reports/summary",
        headers=_auth_headers(token),
        params={
            "period": "custom",
            "start_date": "2026-06-12",
            "end_date": "2026-06-10",
        },
    )
    assert invalid_range.status_code == 400


def test_report_category_groups_totals_by_category(
    test_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = test_client
    token = _register_and_login(client, "owner@example.com")
    category_ids = _category_ids(session_factory)
    user_id = _user_id(session_factory, "owner@example.com")

    _create_transaction(
        session_factory,
        user_id=user_id,
        type="expense",
        amount="20000",
        category_id=category_ids["Makanan"],
        description="makan",
        transaction_date=date(2026, 6, 10),
    )
    _create_transaction(
        session_factory,
        user_id=user_id,
        type="expense",
        amount="30000",
        category_id=category_ids["Makanan"],
        description="kopi",
        transaction_date=date(2026, 6, 11),
    )
    _create_transaction(
        session_factory,
        user_id=user_id,
        type="expense",
        amount="50000",
        category_id=category_ids["Transportasi"],
        description="bensin",
        transaction_date=date(2026, 6, 12),
    )
    _create_transaction(
        session_factory,
        user_id=user_id,
        type="income",
        amount="1000000",
        category_id=category_ids["Gaji"],
        description="gaji",
        transaction_date=date(2026, 6, 13),
    )

    response = client.get(
        "/api/reports/category",
        headers=_auth_headers(token),
        params={"period": "month", "date": "2026-06-15", "type": "expense"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["type"] == "expense"
    assert Decimal(str(payload["total_amount"])) == Decimal("100000.00")
    assert len(payload["items"]) == 2
    assert payload["items"][0]["category_name"] == "Makanan"
    assert Decimal(str(payload["items"][0]["total_amount"])) == Decimal("50000.00")
    assert payload["items"][0]["transaction_count"] == 2
    assert Decimal(str(payload["items"][0]["percentage"])) == Decimal("50.00")
    assert payload["items"][1]["category_name"] == "Transportasi"
    assert Decimal(str(payload["items"][1]["total_amount"])) == Decimal("50000.00")


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


def _category_ids(session_factory: sessionmaker[Session]) -> dict[str, int]:
    with session_factory() as db:
        return {
            name: category_id
            for name, category_id in db.execute(select(Category.name, Category.id))
        }


def _user_id(session_factory: sessionmaker[Session], email: str) -> int:
    with session_factory() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None
        return user.id


def _create_transaction(
    session_factory: sessionmaker[Session],
    *,
    user_id: int,
    type: str,
    amount: str,
    category_id: int,
    description: str,
    transaction_date: date,
) -> None:
    with session_factory() as db:
        db.add(
            Transaction(
                user_id=user_id,
                type=type,
                amount=Decimal(amount),
                category_id=category_id,
                description=description,
                transaction_date=transaction_date,
                source="dashboard_manual",
            )
        )
        db.commit()
