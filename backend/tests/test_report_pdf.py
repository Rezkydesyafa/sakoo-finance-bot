import os
from collections.abc import Iterator
from datetime import date
from decimal import Decimal
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
from app.models import Category, MediaFile, Report, Transaction, User
from app.modules.media.service import resolve_media_file_path
from app.modules.reports.pdf import get_pdf_renderer


class FakePdfRenderer:
    def __init__(self) -> None:
        self.html: str | None = None

    def render_html(self, html: str) -> bytes:
        self.html = html
        return b"%PDF-1.4\n% fake report pdf\n"


@pytest.fixture()
def test_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Iterator[tuple[TestClient, sessionmaker[Session], FakePdfRenderer]]:
    monkeypatch.setenv("STORAGE_PATH", str(tmp_path / "storage"))
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

    fake_renderer = FakePdfRenderer()

    def override_get_db() -> Iterator[Session]:
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_pdf_renderer] = lambda: fake_renderer

    with TestClient(app) as client:
        yield client, TestingSessionLocal, fake_renderer

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    get_settings.cache_clear()


def test_generate_report_pdf_saves_media_and_report(
    test_client: tuple[TestClient, sessionmaker[Session], FakePdfRenderer],
) -> None:
    client, session_factory, fake_renderer = test_client
    token = _register_and_login(client, "owner@example.com")
    category_ids = _category_ids(session_factory)
    user_id = _user_id(session_factory, "owner@example.com")
    _create_transaction(
        session_factory,
        user_id=user_id,
        type="income",
        amount="5000000",
        category_id=category_ids["Gaji"],
        description="gaji juni",
        transaction_date=date(2026, 6, 1),
    )
    _create_transaction(
        session_factory,
        user_id=user_id,
        type="expense",
        amount="20000",
        category_id=category_ids["Makanan"],
        description="makan siang",
        transaction_date=date(2026, 6, 10),
    )

    response = client.post(
        "/api/reports/pdf/generate",
        headers=_auth_headers(token),
        json={"period": "month", "date": "2026-06-15"},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["report"]["status"] == "completed"
    assert payload["report"]["report_type"] == "month"
    assert payload["report"]["period_start"] == "2026-06-01"
    assert payload["report"]["period_end"] == "2026-06-30"
    assert payload["report"]["file_id"] == payload["file"]["id"]
    assert payload["file"]["file_type"] == "pdf"
    assert payload["file"]["mime_type"] == "application/pdf"
    assert payload["file"]["source"] == "report_pdf"
    assert payload["download_url"] == f"/api/media/{payload['file']['id']}/download"

    assert fake_renderer.html is not None
    assert "Laporan Keuangan" in fake_renderer.html
    assert "Ringkasan Kategori" in fake_renderer.html
    assert "Daftar Transaksi" in fake_renderer.html
    assert "Rp5.000.000" in fake_renderer.html
    assert "makan siang" in fake_renderer.html

    with session_factory() as db:
        report = db.get(Report, payload["report"]["id"])
        media_file = db.get(MediaFile, payload["file"]["id"])
        assert report is not None
        assert media_file is not None
        assert report.file_id == media_file.id
        assert media_file.file_type == "pdf"
        assert resolve_media_file_path(media_file).read_bytes().startswith(b"%PDF-1.4")


def test_generate_report_pdf_with_empty_data_still_creates_pdf(
    test_client: tuple[TestClient, sessionmaker[Session], FakePdfRenderer],
) -> None:
    client, session_factory, fake_renderer = test_client
    token = _register_and_login(client, "empty@example.com")

    response = client.post(
        "/api/reports/pdf/generate",
        headers=_auth_headers(token),
        json={
            "period": "custom",
            "start_date": "2026-06-01",
            "end_date": "2026-06-30",
        },
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["report"]["status"] == "completed"
    assert payload["file"]["file_type"] == "pdf"
    assert fake_renderer.html is not None
    assert "Belum ada transaksi pada periode ini." in fake_renderer.html
    assert "Rp0" in fake_renderer.html

    with session_factory() as db:
        report = db.get(Report, payload["report"]["id"])
        media_file = db.get(MediaFile, payload["file"]["id"])
        assert report is not None
        assert media_file is not None
        assert report.file_id == media_file.id
        assert resolve_media_file_path(media_file).is_file()


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
