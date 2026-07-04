import os
from collections.abc import Iterator
from datetime import date, timedelta
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
from app.models import BotLog, Category, Transaction, User, UserPreference
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
        assert "Balas YA" in first.reply_text
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
        assert "Pengeluaran bulan ini" in confirm.reply_text
        assert "Kategori terbesar" in confirm.reply_text


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


def test_pending_transaction_supports_category_date_description_edits(
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

        category_edit = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="edit kategori transport",
            source="telegram_text",
        )
        db.commit()
        assert category_edit.status == "edit_updated"
        assert "Transportasi" in category_edit.reply_text

        date_edit = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="edit tanggal kemarin",
            source="telegram_text",
        )
        db.commit()
        assert date_edit.status == "edit_updated"
        assert (date.today() - timedelta(days=1)).isoformat() in date_edit.reply_text

        note_edit = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="edit catatan makan siang",
            source="telegram_text",
        )
        db.commit()
        assert note_edit.status == "edit_updated"
        assert "makan siang" in note_edit.reply_text

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
        assert transaction.category.name == "Transportasi"
        assert transaction.transaction_date == date.today() - timedelta(days=1)
        assert transaction.description == "makan siang"


def test_pending_transaction_type_can_be_swapped_with_bukan_phrase(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        user = _create_user(db)
        handle_text_transaction(
            db=db,
            user_id=user.id,
            text="keluar 50rb",
            source="telegram_text",
        )
        db.commit()

        edited = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="bukan pengeluaran, pemasukan",
            source="telegram_text",
        )
        db.commit()
        assert edited.status == "edit_updated"
        assert "Pemasukan" in edited.reply_text

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
        assert transaction.type == "income"


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


def test_common_finance_questions_use_local_insights_before_llm(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_answer(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("LLM chat should not be called for supported insight questions")

    monkeypatch.setattr(
        "app.modules.transactions.service.answer_finance_question_with_llm",
        fail_answer,
    )

    with session_factory() as db:
        user = _create_user(db)
        food = db.scalar(select(Category).where(Category.name == "Makanan"))
        db.add_all(
            [
                Transaction(
                    user_id=user.id,
                    type="income",
                    amount=Decimal("100000.00"),
                    category_id=db.scalar(select(Category).where(Category.name == "Gaji")).id,
                    description="gaji",
                    transaction_date=date.today(),
                    source="telegram_text",
                ),
                Transaction(
                    user_id=user.id,
                    type="expense",
                    amount=Decimal("75000.00"),
                    category_id=food.id if food else None,
                    description="makan",
                    transaction_date=date.today(),
                    source="telegram_text",
                ),
            ]
        )
        db.commit()

        spending = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="bulan ini aku boros gak?",
            source="telegram_text",
        )
        advice = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="saran hemat minggu ini?",
            source="telegram_text",
        )
        reason = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="kenapa saldo cepat habis?",
            source="telegram_text",
        )

    assert spending.status == "spending_check"
    assert "Pengeluaran bulan ini" in spending.reply_text
    assert advice.status == "saving_advice"
    assert "Saran cepat" in advice.reply_text
    assert reason.status == "cashflow_reason"
    assert "Saldo cepat habis" in reason.reply_text


def test_reply_style_preference_is_saved_and_used(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        user = _create_user(db)
        preference = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="gaya bahasa singkat",
            source="telegram_text",
        )
        db.commit()

        saved = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="beli makan 20 ribu",
            source="telegram_text",
        )
        db.commit()

        stored_preference = db.scalar(
            select(UserPreference).where(UserPreference.user_id == user.id)
        )
        assert preference.status == "preference_updated"
        assert stored_preference is not None
        assert stored_preference.reply_style == "short"
        assert saved.status == "saved"
        assert saved.reply_text.startswith("Oke, Tercatat.")


def test_unknown_finance_question_uses_llm_chat(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_answer(message: str, **kwargs: object) -> str:
        calls.append({"message": message, **kwargs})
        return "Bulan ini pengeluaranmu masih aman. Mulai pantau kategori terbesar dulu."

    monkeypatch.setattr(
        "app.modules.transactions.service.answer_finance_question_with_llm",
        fake_answer,
    )

    with session_factory() as db:
        user = _create_user(db)
        result = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="menurutmu keuangan bulan ini aman nggak?",
            source="telegram_text",
        )

    assert result.status == "finance_chat"
    assert "pengeluaranmu" in result.reply_text
    assert calls and "Pengeluaran bulan ini" in str(calls[0]["context"])


def test_unknown_non_finance_question_does_not_use_llm_chat(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_answer(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("LLM chat should not be called")

    monkeypatch.setattr(
        "app.modules.transactions.service.answer_finance_question_with_llm",
        fail_answer,
    )

    with session_factory() as db:
        user = _create_user(db)
        result = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="ceritakan cuaca bandung",
            source="telegram_text",
        )

    assert result.status == "unknown"
    assert "Aku belum paham" in result.reply_text


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
