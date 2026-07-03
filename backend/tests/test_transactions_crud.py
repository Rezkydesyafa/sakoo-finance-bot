import os
from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-jwt-secret-minimum-32-characters"
os.environ["LLM_PROVIDER"] = "none"

from app.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import Category, Transaction


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


def test_user_can_crud_income_and_expense_transactions(
    test_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = test_client
    token = _register_and_login(client, "owner@example.com")
    category_ids = _category_ids(session_factory)

    expense_response = client.post(
        "/api/transactions",
        headers=_auth_headers(token),
        json={
            "type": "expense",
            "amount": "18000",
            "category_id": category_ids["Makanan"],
            "description": "beli kopi",
            "transaction_date": "2026-06-27",
        },
    )
    assert expense_response.status_code == 201, expense_response.text
    expense = expense_response.json()
    assert expense["source"] == "dashboard_manual"
    assert expense["type"] == "expense"
    assert Decimal(str(expense["amount"])) == Decimal("18000.00")

    income_response = client.post(
        "/api/transactions",
        headers=_auth_headers(token),
        json={
            "type": "income",
            "amount": "2000000",
            "category_id": category_ids["Gaji"],
            "description": "gaji masuk",
            "transaction_date": "2026-06-27",
        },
    )
    assert income_response.status_code == 201, income_response.text
    assert income_response.json()["source"] == "dashboard_manual"

    list_response = client.get("/api/transactions", headers=_auth_headers(token))
    assert list_response.status_code == 200
    list_payload = list_response.json()
    assert len(list_payload["items"]) == 2
    assert list_payload["total"] == 2
    assert list_payload["limit"] == 50
    assert list_payload["offset"] == 0

    transaction_id = expense["id"]
    detail_response = client.get(
        f"/api/transactions/{transaction_id}",
        headers=_auth_headers(token),
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["description"] == "beli kopi"

    update_response = client.put(
        f"/api/transactions/{transaction_id}",
        headers=_auth_headers(token),
        json={
            "amount": "25000",
            "description": "beli kopi dan roti",
        },
    )
    assert update_response.status_code == 200, update_response.text
    updated = update_response.json()
    assert Decimal(str(updated["amount"])) == Decimal("25000.00")
    assert updated["description"] == "beli kopi dan roti"
    assert updated["source"] == "dashboard_manual"

    delete_response = client.delete(
        f"/api/transactions/{transaction_id}",
        headers=_auth_headers(token),
    )
    assert delete_response.status_code == 204

    assert (
        client.get(
            f"/api/transactions/{transaction_id}",
            headers=_auth_headers(token),
        ).status_code
        == 404
    )

    with session_factory() as db:
        remaining = list(db.scalars(select(Transaction)))
        assert len(remaining) == 1
        assert remaining[0].type == "income"
        assert remaining[0].source == "dashboard_manual"


def test_transaction_rejects_category_from_different_type(
    test_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = test_client
    token = _register_and_login(client, "owner@example.com")
    category_ids = _category_ids(session_factory)

    response = client.post(
        "/api/transactions",
        headers=_auth_headers(token),
        json={
            "type": "income",
            "amount": "500000",
            "category_id": category_ids["Makanan"],
            "description": "income with expense category",
            "transaction_date": "2026-06-27",
        },
    )

    assert response.status_code == 400


def test_transaction_parse_endpoint_uses_backend_parser(
    test_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = test_client
    token = _register_and_login(client, "chat-owner@example.com")

    response = client.post(
        "/api/transactions/parse",
        headers=_auth_headers(token),
        json={"text": "jajan kopi 18k"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "saved"
    assert payload["transaction_id"] is not None
    assert "Saldo sekarang" in payload["reply_text"]

    with session_factory() as db:
        transaction = db.get(Transaction, payload["transaction_id"])
        assert transaction is not None
        assert transaction.source == "dashboard_manual"
        assert transaction.description == "jajan kopi"
        assert transaction.amount == Decimal("18000.00")


def test_transaction_list_supports_filters_pagination_and_newest_sort(
    test_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = test_client
    token = _register_and_login(client, "owner@example.com")
    category_ids = _category_ids(session_factory)

    _create_transaction(
        client,
        token,
        type="expense",
        amount="10000",
        category_id=category_ids["Makanan"],
        description="kopi lama",
        transaction_date="2026-06-25",
    )
    newer_expense = _create_transaction(
        client,
        token,
        type="expense",
        amount="20000",
        category_id=category_ids["Makanan"],
        description="kopi baru",
        transaction_date="2026-06-27",
    )
    _create_transaction(
        client,
        token,
        type="income",
        amount="2000000",
        category_id=category_ids["Gaji"],
        description="gaji",
        transaction_date="2026-06-26",
    )

    filtered = client.get(
        "/api/transactions",
        headers=_auth_headers(token),
        params={
            "start_date": "2026-06-26",
            "end_date": "2026-06-27",
            "category_id": category_ids["Makanan"],
            "type": "expense",
            "limit": 10,
            "offset": 0,
        },
    )
    assert filtered.status_code == 200, filtered.text
    filtered_payload = filtered.json()
    assert filtered_payload["total"] == 1
    assert filtered_payload["items"][0]["id"] == newer_expense["id"]
    assert filtered_payload["items"][0]["description"] == "kopi baru"

    first_page = client.get(
        "/api/transactions",
        headers=_auth_headers(token),
        params={"limit": 2, "offset": 0},
    )
    assert first_page.status_code == 200
    first_page_payload = first_page.json()
    assert first_page_payload["total"] == 3
    assert first_page_payload["limit"] == 2
    assert first_page_payload["offset"] == 0
    assert first_page_payload["has_next"] is True
    assert [item["transaction_date"] for item in first_page_payload["items"]] == [
        "2026-06-27",
        "2026-06-26",
    ]

    second_page = client.get(
        "/api/transactions",
        headers=_auth_headers(token),
        params={"limit": 2, "offset": 2},
    )
    assert second_page.status_code == 200
    second_page_payload = second_page.json()
    assert second_page_payload["total"] == 3
    assert second_page_payload["has_next"] is False
    assert len(second_page_payload["items"]) == 1
    assert second_page_payload["items"][0]["transaction_date"] == "2026-06-25"

    invalid_range = client.get(
        "/api/transactions",
        headers=_auth_headers(token),
        params={"start_date": "2026-06-28", "end_date": "2026-06-27"},
    )
    assert invalid_range.status_code == 400


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


def _create_transaction(
    client: TestClient,
    token: str,
    *,
    type: str,
    amount: str,
    category_id: int,
    description: str,
    transaction_date: str,
) -> dict[str, object]:
    response = client.post(
        "/api/transactions",
        headers=_auth_headers(token),
        json={
            "type": type,
            "amount": amount,
            "category_id": category_id,
            "description": description,
            "transaction_date": transaction_date,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _category_ids(session_factory: sessionmaker[Session]) -> dict[str, int]:
    with session_factory() as db:
        return {
            name: category_id
            for name, category_id in db.execute(select(Category.name, Category.id))
        }


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
