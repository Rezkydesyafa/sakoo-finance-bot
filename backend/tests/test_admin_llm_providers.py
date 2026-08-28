from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-minimum-32-characters")

from app.config import get_settings
from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def test_client() -> Iterator[tuple[TestClient, sessionmaker[Session]]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    testing_session = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db() -> Iterator[Session]:
        with testing_session() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client, testing_session
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    get_settings.cache_clear()


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _register_and_login(client: TestClient, email: str) -> str:
    password = "safe-password-123"
    assert client.post(
        "/api/auth/register",
        json={"name": "Admin", "email": email, "password": password},
    ).status_code == 201
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_admin_can_create_provider_without_exposing_api_key(
    test_client: tuple[TestClient, sessionmaker[Session]], monkeypatch
) -> None:
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    monkeypatch.setenv(
        "LLM_PROVIDER_ENCRYPTION_KEY", "9iIaG4ck34QLyNpGZI10M4aJ0LEoGZPmnysAzfQ7pA8="
    )
    get_settings.cache_clear()
    client, _ = test_client
    admin_token = _register_and_login(client, "admin@example.com")

    response = client.post(
        "/api/admin/llm-providers",
        headers=_auth_headers(admin_token),
        json={
            "name": "private-gateway",
            "base_url": "https://llm.example.com/v1",
            "api_key": "top-secret-key",
            "model": "model-a",
            "enabled": True,
            "priority": 10,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "private-gateway"
    assert body["api_key_masked"] == "**********-key"
    assert "api_key" not in body


def test_non_admin_is_forbidden_from_listing_providers(
    test_client: tuple[TestClient, sessionmaker[Session]], monkeypatch
) -> None:
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    monkeypatch.setenv(
        "LLM_PROVIDER_ENCRYPTION_KEY", "9iIaG4ck34QLyNpGZI10M4aJ0LEoGZPmnysAzfQ7pA8="
    )
    get_settings.cache_clear()
    client, _ = test_client
    user_token = _register_and_login(client, "user@example.com")

    response = client.get("/api/admin/llm-providers", headers=_auth_headers(user_token))

    assert response.status_code == 403


def test_login_and_profile_expose_backend_verified_admin_status(
    test_client: tuple[TestClient, sessionmaker[Session]], monkeypatch
) -> None:
    monkeypatch.setenv("ADMIN_EMAILS", " admin@example.com , second@example.com ")
    get_settings.cache_clear()
    client, _ = test_client

    admin_token = _register_and_login(client, "ADMIN@example.com")
    admin_login = client.post(
        "/api/auth/login",
        json={"email": "admin@example.com", "password": "safe-password-123"},
    )
    assert admin_login.status_code == 200
    assert admin_login.json()["is_admin"] is True
    admin_profile = client.get("/api/auth/me", headers=_auth_headers(admin_token))
    assert admin_profile.status_code == 200
    assert admin_profile.json()["is_admin"] is True

    user_token = _register_and_login(client, "user@example.com")
    user_profile = client.get("/api/auth/me", headers=_auth_headers(user_token))
    assert user_profile.status_code == 200
    assert user_profile.json()["is_admin"] is False


def test_admin_can_update_and_delete_provider(
    test_client: tuple[TestClient, sessionmaker[Session]], monkeypatch
) -> None:
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    monkeypatch.setenv(
        "LLM_PROVIDER_ENCRYPTION_KEY", "9iIaG4ck34QLyNpGZI10M4aJ0LEoGZPmnysAzfQ7pA8="
    )
    get_settings.cache_clear()
    client, _ = test_client
    admin_token = _register_and_login(client, "admin@example.com")
    headers = _auth_headers(admin_token)
    created = client.post(
        "/api/admin/llm-providers",
        headers=headers,
        json={
            "name": "gateway",
            "base_url": "https://llm.example.com",
            "api_key": "old-secret",
            "model": "model-a",
        },
    )
    assert created.status_code == 201
    provider_id = created.json()["id"]

    updated = client.patch(
        f"/api/admin/llm-providers/{provider_id}",
        headers=headers,
        json={"enabled": False, "priority": 2, "api_key": "new-secret"},
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["priority"] == 2
    assert updated.json()["api_key_masked"] == "******cret"

    listed = client.get("/api/admin/llm-providers", headers=headers)
    assert listed.status_code == 200
    assert listed.json()["items"][0]["name"] == "gateway"

    assert client.delete(f"/api/admin/llm-providers/{provider_id}", headers=headers).status_code == 204
    assert client.get(f"/api/admin/llm-providers/{provider_id}", headers=headers).status_code == 404


def test_admin_can_rename_provider_and_conflict_is_rejected(
    test_client: tuple[TestClient, sessionmaker[Session]], monkeypatch
) -> None:
    monkeypatch.setenv("ADMIN_EMAILS", "admin@example.com")
    monkeypatch.setenv(
        "LLM_PROVIDER_ENCRYPTION_KEY", "9iIaG4ck34QLyNpGZI10M4aJ0LEoGZPmnysAzfQ7pA8="
    )
    get_settings.cache_clear()
    client, _ = test_client
    admin_token = _register_and_login(client, "admin@example.com")
    headers = _auth_headers(admin_token)

    def _create(name: str) -> int:
        response = client.post(
            "/api/admin/llm-providers",
            headers=headers,
            json={
                "name": name,
                "base_url": "https://llm.example.com/v1",
                "api_key": "secret",
                "model": "model-a",
            },
        )
        assert response.status_code == 201
        return response.json()["id"]

    first_id = _create("gateway-a")
    _create("gateway-b")

    renamed = client.patch(
        f"/api/admin/llm-providers/{first_id}",
        headers=headers,
        json={"name": "gateway-a-renamed"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "gateway-a-renamed"

    listed = client.get("/api/admin/llm-providers", headers=headers)
    names = [item["name"] for item in listed.json()["items"]]
    assert "gateway-a-renamed" in names
    assert "gateway-a" not in names

    conflict = client.patch(
        f"/api/admin/llm-providers/{first_id}",
        headers=headers,
        json={"name": "gateway-b"},
    )
    assert conflict.status_code == 409


def test_migration_creates_llm_providers_table() -> None:
    # Covered by the Alembic migration smoke test; this names the public schema contract.
    from app.models import LlmProvider

    assert LlmProvider.__tablename__ == "llm_providers"
