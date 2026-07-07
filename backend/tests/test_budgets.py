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
os.environ["LLM_PROVIDER"] = "none"

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


def test_budget_api_upsert_get_delete_and_isolates_users(
    test_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = test_client
    token_a = _register_and_login(client, "budget-a@example.com")
    token_b = _register_and_login(client, "budget-b@example.com")
    ids = _category_ids(session_factory)

    response = client.put(
        f"/api/budgets/{ids['Makanan']}",
        headers=_auth_headers(token_a),
        json={"monthly_limit": "600000"},
    )
    assert response.status_code == 200, response.text
    assert Decimal(str(response.json()["monthly_limit"])) == Decimal("600000")

    with session_factory() as db:
        user_a = _user(db, "budget-a@example.com")
        db.add(
            Transaction(
                user_id=user_a.id,
                type="expense",
                amount=Decimal("420000.00"),
                category_id=ids["Makanan"],
                description="makan bulan ini",
                transaction_date=date.today(),
                source="dashboard_manual",
                status="confirmed",
            )
        )
        db.commit()

    list_a = client.get("/api/budgets", headers=_auth_headers(token_a))
    assert list_a.status_code == 200, list_a.text
    payload_a = list_a.json()
    assert Decimal(str(payload_a["total_budgeted"])) == Decimal("600000")
    assert Decimal(str(payload_a["total_spent"])) == Decimal("420000")
    assert Decimal(str(payload_a["total_remaining"])) == Decimal("180000")
    item = payload_a["items"][0]
    assert item["category_name"] == "Makanan"
    assert Decimal(str(item["spent"])) == Decimal("420000")
    assert Decimal(str(item["remaining"])) == Decimal("180000")
    assert item["status"] == "warning"

    list_b = client.get("/api/budgets", headers=_auth_headers(token_b))
    assert list_b.status_code == 200, list_b.text
    assert list_b.json()["items"] == []

    delete_response = client.delete(
        f"/api/budgets/{ids['Makanan']}",
        headers=_auth_headers(token_a),
    )
    assert delete_response.status_code == 204, delete_response.text
    assert client.get("/api/budgets", headers=_auth_headers(token_a)).json()["items"] == []


def test_budget_api_rejects_income_only_and_other_user_category(
    test_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = test_client
    token_a = _register_and_login(client, "owner@example.com")
    token_b = _register_and_login(client, "other@example.com")
    ids = _category_ids(session_factory)

    income_response = client.put(
        f"/api/budgets/{ids['Gaji']}",
        headers=_auth_headers(token_a),
        json={"monthly_limit": "1000000"},
    )
    assert income_response.status_code == 404

    with session_factory() as db:
        other = _user(db, "other@example.com")
        category = Category(name="Nongkrong", type="expense", user_id=other.id)
        db.add(category)
        db.commit()
        other_category_id = category.id

    other_category_response = client.put(
        f"/api/budgets/{other_category_id}",
        headers=_auth_headers(token_a),
        json={"monthly_limit": "250000"},
    )
    assert other_category_response.status_code == 404

    owner_category_response = client.put(
        f"/api/budgets/{other_category_id}",
        headers=_auth_headers(token_b),
        json={"monthly_limit": "250000"},
    )
    assert owner_category_response.status_code == 200, owner_category_response.text


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
    assert register_response.status_code == 201, register_response.text

    login_response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200, login_response.text
    return login_response.json()["access_token"]


def _category_ids(session_factory: sessionmaker[Session]) -> dict[str, int]:
    with session_factory() as db:
        return {
            name: category_id
            for name, category_id in db.execute(select(Category.name, Category.id))
        }


def _user(db: Session, email: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    assert user is not None
    return user


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
