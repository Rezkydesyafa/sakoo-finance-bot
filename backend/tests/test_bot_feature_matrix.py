import os
from collections.abc import Iterator
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-jwt-secret-minimum-32-characters"
os.environ["LLM_PROVIDER"] = "none"

from app.database import Base
from app.models import Category, Job, Transaction, User
from app.modules.bot.response_templates import format_help_response
from app.modules.parser.intent_router import COMMAND_INTENTS
from app.modules.reports.bot_pdf import handle_report_pdf_command
from app.modules.telegram.commands import BOT_COMMANDS
from app.modules.transactions.service import (
    handle_telegram_text_transaction,
    handle_whatsapp_text_transaction,
)


@pytest.fixture()
def session_factory(monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker[Session]]:
    monkeypatch.setenv("LLM_PROVIDER", "none")
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
                Category(name="Tagihan", type="expense"),
                Category(name="Belanja", type="expense"),
                Category(name="Pendidikan", type="expense"),
                Category(name="Gaji", type="income"),
                Category(name="Uang Saku", type="income"),
                Category(name="Lainnya", type="expense"),
                Category(name="Lainnya", type="income"),
            ]
        )
        db.commit()

    yield TestingSessionLocal

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.mark.parametrize(
    ("message", "status", "reply_part"),
    [
        ("/help", "help", "Sakoo"),
        ("saldo", "get_balance", "Sisa saldo"),
        ("list pengeluaran", "list_expense", "List pengeluaran"),
        ("list pemasukan", "list_income", "List pemasukan"),
        ("laporan bulan ini", "get_report", "Laporan bulan ini"),
        ("riwayat transaksi", "recent_transactions", "Riwayat transaksi"),
        ("bulan ini aku boros gak?", "spending_check", "Pengeluaran bulan ini"),
        ("tips hemat minggu ini", "saving_advice", "Batas aman harian"),
        ("cari kopi", "transaction_search", "kopi susu"),
        ("kategori budget apa saja", "budget_category_list", "Makanan"),
        ("list budget", "budget_list", "Belum ada budget"),
        ("gaya bahasa singkat", "preference_updated", "lebih singkat"),
        ("kamu bisa bantu apa saja?", "bot_profile", "catat transaksi"),
    ],
)
@pytest.mark.parametrize(
    ("channel", "handler"),
    [
        ("whatsapp", handle_whatsapp_text_transaction),
        ("telegram", handle_telegram_text_transaction),
    ],
)
def test_chatbot_text_feature_matrix_for_whatsapp_and_telegram(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
    channel: str,
    handler,
    message: str,
    status: str,
    reply_part: str,
) -> None:
    def fail_llm(*_args: object, **_kwargs: object) -> str:
        raise AssertionError(f"{channel} deterministic command should not call LLM")

    monkeypatch.setattr(
        "app.modules.transactions.service.answer_finance_question_with_llm",
        fail_llm,
    )
    with session_factory() as db:
        user = _create_user(db, email=f"{channel}-{status}@example.com")
        _seed_transactions(db, user.id)

        result = handler(db=db, user_id=user.id, text=message)

    assert result.status == status
    assert reply_part in result.reply_text


@pytest.mark.parametrize(
    ("channel", "handler"),
    [
        ("whatsapp", handle_whatsapp_text_transaction),
        ("telegram", handle_telegram_text_transaction),
    ],
)
def test_budget_conversation_flow_for_whatsapp_and_telegram(
    session_factory: sessionmaker[Session],
    channel: str,
    handler,
) -> None:
    with session_factory() as db:
        user = _create_user(db, email=f"budget-{channel}@example.com")
        saved = handler(db=db, user_id=user.id, text="set budget makan 600rb")
        remaining = handler(db=db, user_id=user.id, text="budget makan tinggal berapa?")

    assert saved.status == "budget_saved"
    assert "Budget Makanan: Rp600.000" in saved.reply_text
    assert remaining.status == "budget_remaining"
    assert "Sisa Rp600.000" in remaining.reply_text


@pytest.mark.parametrize("platform", ["whatsapp", "telegram"])
def test_export_pdf_command_queues_for_whatsapp_and_telegram(
    session_factory: sessionmaker[Session],
    platform: str,
) -> None:
    queued: list[dict[str, object]] = []

    with session_factory() as db:
        user = _create_user(db, email=f"export-{platform}@example.com")
        result = handle_report_pdf_command(
            db=db,
            user_id=user.id,
            text="/export",
            platform=platform,
            enqueue=lambda **kwargs: queued.append(kwargs),
            notify_chat_id="chat-1",
            notify_session="default" if platform == "whatsapp" else None,
        )
        job = db.scalar(select(Job))

    assert result is not None
    assert result.status == "queued"
    assert job is not None
    assert job.job_type == "report_pdf"
    assert queued[0]["notify_platform"] == platform


def test_registered_telegram_commands_are_parseable_and_visible_in_help() -> None:
    registered = {f"/{item['command']}" for item in BOT_COMMANDS}

    assert registered <= set(COMMAND_INTENTS)
    for command in registered:
        assert command in format_help_response()


def _create_user(db: Session, *, email: str) -> User:
    user = User(name="Bot Matrix User", email=email, password_hash="hashed-password")
    db.add(user)
    db.flush()
    return user


def _seed_transactions(db: Session, user_id: int) -> None:
    food = db.scalar(select(Category).where(Category.name == "Makanan"))
    income = db.scalar(select(Category).where(Category.name == "Gaji"))
    db.add_all(
        [
            Transaction(
                user_id=user_id,
                type="income",
                amount=Decimal("1000000.00"),
                category_id=income.id if income else None,
                description="gaji",
                transaction_date=date.today(),
                source="dashboard_manual",
                status="confirmed",
            ),
            Transaction(
                user_id=user_id,
                type="expense",
                amount=Decimal("20000.00"),
                category_id=food.id if food else None,
                description="kopi susu",
                transaction_date=date.today(),
                source="dashboard_manual",
                status="confirmed",
            ),
        ]
    )
    db.commit()
