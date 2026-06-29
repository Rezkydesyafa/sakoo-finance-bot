import os
from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-jwt-secret-minimum-32-characters"
os.environ["LLM_PROVIDER"] = "none"

from app.config import get_settings
from app.database import Base
from app.models import BotLog, Category, Transaction, User
from app.modules.transactions.service import handle_text_transaction


@pytest.fixture()
def session_factory(monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker[Session]]:
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.setenv("BOT_REPLY_STYLE", "friendly")
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
                Category(name="Tagihan", type="expense"),
                Category(name="Belanja", type="expense"),
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
    get_settings.cache_clear()


def test_pending_transaction_can_be_confirmed(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as db:
        user = _create_user(db)
        first = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="keluar 20 ribu",
            source="telegram_text",
        )
        db.commit()

        assert first.status == "needs_confirmation"
        assert "Apakah benar" in first.reply_text
        assert db.scalar(select(Transaction)) is None

        confirm = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="ya",
            source="telegram_text",
        )
        db.commit()

        transaction = db.scalar(select(Transaction))
        assert confirm.status == "saved"
        assert transaction is not None
        assert transaction.amount == Decimal("20000.00")
        assert transaction.type == "expense"
        assert "Saldo sekarang" in confirm.reply_text


def test_missing_amount_can_be_filled_step_by_step(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        user = _create_user(db)
        first = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="beli makan",
            source="whatsapp_text",
        )
        db.commit()

        assert first.status == "needs_confirmation"
        assert "nominal belum terbaca" in first.reply_text

        amount_reply = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="20rb",
            source="whatsapp_text",
        )
        db.commit()

        assert amount_reply.status == "edit_updated"
        assert "Rp20.000" in amount_reply.reply_text

        confirm = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="oke",
            source="whatsapp_text",
        )
        db.commit()

        transaction = db.scalar(select(Transaction))
        assert confirm.status == "saved"
        assert transaction is not None
        assert transaction.amount == Decimal("20000.00")
        assert transaction.category.name == "Makanan"


def test_pending_transaction_can_be_edited_before_save(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        user = _create_user(db)
        first = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="keluar 50rb",
            source="telegram_text",
        )
        db.commit()
        assert first.status == "needs_confirmation"

        edited = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="edit nominal 60000 makanan",
            source="telegram_text",
        )
        db.commit()
        assert edited.status == "edit_updated"
        assert "Rp60.000" in edited.reply_text
        assert "Makanan" in edited.reply_text

        confirm = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="ya",
            source="telegram_text",
        )
        db.commit()

        transaction = db.scalar(select(Transaction))
        assert confirm.status == "saved"
        assert transaction is not None
        assert transaction.amount == Decimal("60000.00")
        assert transaction.category.name == "Makanan"


def test_lightweight_responses_and_spending_check(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        user = _create_user(db)
        thanks = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="makasih",
            source="telegram_text",
        )
        assert thanks.status == "small_talk"
        assert "Sama-sama" in thanks.reply_text

        spending = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="hari ini boros ga?",
            source="telegram_text",
        )
        assert spending.status == "spending_check"
        assert "Pengeluaran hari ini" in spending.reply_text


def test_cancel_pending_transaction(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as db:
        user = _create_user(db)
        handle_text_transaction(
            db=db,
            user_id=user.id,
            text="keluar 20 ribu",
            source="telegram_text",
        )
        db.commit()

        cancelled = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="batal",
            source="telegram_text",
        )
        db.commit()

        assert cancelled.status == "cancelled"
        assert db.scalar(select(Transaction)) is None
        pending_log = db.scalar(select(BotLog).where(BotLog.status == "cancelled_transaction"))
        assert pending_log is not None


def _create_user(db: Session) -> User:
    user = User(
        name="Conversation User",
        email="conversation@example.com",
        password_hash="hashed-password",
    )
    db.add(user)
    db.flush()
    return user
