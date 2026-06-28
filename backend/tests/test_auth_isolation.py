import os
from collections.abc import Iterator
from datetime import datetime, timezone

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
from app.models import AccountLinkingCode, Transaction, User
from app.modules.auth.security import verify_password


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


def test_register_hashes_password(test_client: tuple[TestClient, sessionmaker[Session]]) -> None:
    client, session_factory = test_client
    plain_password = "super-secret-password"

    response = client.post(
        "/api/auth/register",
        json={
            "name": "User A",
            "email": "user-a@example.com",
            "password": plain_password,
        },
    )

    assert response.status_code == 201
    assert "password" not in response.json()

    with session_factory() as db:
        user = db.scalar(select(User).where(User.email == "user-a@example.com"))
        assert user is not None
        assert user.password_hash != plain_password
        assert user.password_hash.startswith(("$2a$", "$2b$", "$2y$"))
        assert verify_password(plain_password, user.password_hash)


def test_transaction_queries_are_isolated_by_current_user(
    test_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = test_client
    token_a = _register_and_login(client, "user-a@example.com")
    token_b = _register_and_login(client, "user-b@example.com")

    create_response = client.post(
        "/api/transactions",
        headers=_auth_headers(token_a),
        json={
            "type": "expense",
            "amount": "18000",
            "description": "beli kopi",
            "transaction_date": "2026-06-27",
        },
    )
    assert create_response.status_code == 201
    transaction_id = create_response.json()["id"]

    user_b_list = client.get("/api/transactions", headers=_auth_headers(token_b))
    assert user_b_list.status_code == 200
    assert user_b_list.json()["items"] == []
    assert user_b_list.json()["total"] == 0
    assert (
        client.get(
            f"/api/transactions/{transaction_id}",
            headers=_auth_headers(token_b),
        ).status_code
        == 404
    )
    assert (
        client.put(
            f"/api/transactions/{transaction_id}",
            headers=_auth_headers(token_b),
            json={"description": "edited by user b"},
        ).status_code
        == 404
    )
    assert (
        client.delete(
            f"/api/transactions/{transaction_id}",
            headers=_auth_headers(token_b),
        ).status_code
        == 404
    )

    owner_response = client.get(
        f"/api/transactions/{transaction_id}",
        headers=_auth_headers(token_a),
    )
    assert owner_response.status_code == 200
    assert owner_response.json()["description"] == "beli kopi"

    with session_factory() as db:
        transaction = db.get(Transaction, transaction_id)
        assert transaction is not None
        assert transaction.description == "beli kopi"


def test_private_transaction_endpoint_requires_token(
    test_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = test_client

    response = client.get("/api/transactions")

    assert response.status_code in {401, 403}


def test_create_linking_code_requires_token(
    test_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, _session_factory = test_client

    response = client.post("/api/auth/linking-codes")

    assert response.status_code in {401, 403}


def test_create_linking_code_returns_command_and_expires_previous_code(
    test_client: tuple[TestClient, sessionmaker[Session]],
) -> None:
    client, session_factory = test_client
    token = _register_and_login(client, "linking@example.com")

    first_response = client.post(
        "/api/auth/linking-codes",
        headers=_auth_headers(token),
    )
    second_response = client.post(
        "/api/auth/linking-codes",
        headers=_auth_headers(token),
    )

    assert first_response.status_code == 201, first_response.text
    assert second_response.status_code == 201, second_response.text
    first_payload = first_response.json()
    second_payload = second_response.json()
    assert len(first_payload["code"]) == 6
    assert first_payload["command"] == f"hubungkan {first_payload['code']}"
    assert len(second_payload["code"]) == 6
    assert second_payload["command"] == f"hubungkan {second_payload['code']}"
    assert first_payload["code"] != second_payload["code"]

    with session_factory() as db:
        codes = list(
            db.scalars(
                select(AccountLinkingCode).order_by(AccountLinkingCode.created_at)
            )
        )
        assert len(codes) == 2
        assert _as_utc(codes[0].expired_at) <= datetime.now(timezone.utc)
        assert _as_utc(codes[1].expired_at) > datetime.now(timezone.utc)


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


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
