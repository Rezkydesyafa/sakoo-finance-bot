import os
from collections.abc import Iterator
from pathlib import Path

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
from app.models import MediaFile


@pytest.fixture()
def test_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session], Path]]:
    storage_path = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_PATH", str(storage_path))
    monkeypatch.setenv("MEDIA_RECEIPT_MAX_BYTES", "10")
    monkeypatch.setenv("MEDIA_DEFAULT_MAX_BYTES", "20")
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
        yield client, TestingSessionLocal, storage_path

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    get_settings.cache_clear()


def test_user_can_upload_and_download_own_receipt(
    test_client: tuple[TestClient, sessionmaker[Session], Path],
) -> None:
    client, session_factory, storage_path = test_client
    token = _register_and_login(client, "owner@example.com")
    content = b"receipt"

    upload_response = client.post(
        "/api/media",
        headers=_auth_headers(token),
        data={"file_type": "receipt", "source": "dashboard_upload"},
        files={"file": ("receipt.jpg", content, "image/jpeg")},
    )

    assert upload_response.status_code == 201, upload_response.text
    payload = upload_response.json()
    assert payload["file_type"] == "receipt"
    assert payload["original_filename"] == "receipt.jpg"
    assert payload["mime_type"] == "image/jpeg"
    assert payload["size"] == len(content)
    assert "stored_path" not in payload

    with session_factory() as db:
        media_file = db.get(MediaFile, payload["id"])
        assert media_file is not None
        assert Path(media_file.stored_path).parts[:2] == (
            f"user_{media_file.user_id}",
            "receipt",
        )
        saved_path = storage_path / Path(media_file.stored_path)
        assert saved_path.is_file()
        assert saved_path.read_bytes() == content

    download_response = client.get(
        f"/api/media/{payload['id']}/download",
        headers=_auth_headers(token),
    )

    assert download_response.status_code == 200
    assert download_response.content == content
    assert download_response.headers["content-type"].startswith("image/jpeg")


def test_media_download_is_isolated_by_current_user(
    test_client: tuple[TestClient, sessionmaker[Session], Path],
) -> None:
    client, _session_factory, _storage_path = test_client
    token_a = _register_and_login(client, "user-a@example.com")
    token_b = _register_and_login(client, "user-b@example.com")

    upload_response = client.post(
        "/api/media",
        headers=_auth_headers(token_a),
        data={"file_type": "receipt", "source": "dashboard_upload"},
        files={"file": ("receipt.png", b"receipt", "image/png")},
    )
    assert upload_response.status_code == 201, upload_response.text
    media_id = upload_response.json()["id"]

    missing_for_user_b = client.get(
        f"/api/media/{media_id}/download",
        headers=_auth_headers(token_b),
    )
    assert missing_for_user_b.status_code == 404

    unauthenticated = client.get(f"/api/media/{media_id}/download")
    assert unauthenticated.status_code in {401, 403}


def test_receipt_upload_rejects_file_over_size_limit(
    test_client: tuple[TestClient, sessionmaker[Session], Path],
) -> None:
    client, session_factory, storage_path = test_client
    token = _register_and_login(client, "owner@example.com")

    response = client.post(
        "/api/media",
        headers=_auth_headers(token),
        data={"file_type": "receipt", "source": "dashboard_upload"},
        files={"file": ("too-large.jpg", b"12345678901", "image/jpeg")},
    )

    assert response.status_code == 413
    with session_factory() as db:
        assert db.scalar(select(MediaFile)) is None
    assert not any(storage_path.rglob("*"))


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
