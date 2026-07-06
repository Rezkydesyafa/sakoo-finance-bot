import os
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["JWT_SECRET"] = "test-jwt-secret-minimum-32-characters"
os.environ["LLM_PROVIDER"] = "none"

from app.config import get_settings
from app.database import Base
from app.models import BotLog, Category, MediaFile, Receipt, Transaction, User, UserPreference
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
        assert "Balas *YA*" in first.reply_text
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
        assert transaction.status == "confirmed"
        assert confirm.transaction_id == transaction.id
        assert "Tercatat" in confirm.reply_text
        assert "Pengeluaran bulan ini" not in confirm.reply_text


def test_pending_transaction_expires_before_confirmation(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        user = _create_user(db)
        first = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="keluar 20 ribu",
            source="telegram_text",
        )
        db.commit()
        pending_log = db.scalar(select(BotLog).where(BotLog.status == "pending_transaction"))
        assert first.status == "needs_confirmation"
        assert pending_log is not None
        pending_log.created_at = datetime.utcnow() - timedelta(minutes=31)
        db.commit()

        confirm = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="ya",
            source="telegram_text",
        )
        db.commit()

        assert confirm.status == "no_pending_confirmation"
        assert "kedaluwarsa" in confirm.reply_text
        assert db.scalar(select(Transaction)) is None
        assert db.scalar(select(BotLog).where(BotLog.status == "expired_transaction")) is not None


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
        assert "belum menemukan nominalnya" in first.reply_text

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
        health = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="keuangan bulan ini aman gak?",
            source="telegram_text",
        )
        cutback = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="apa yang harus dikurangi?",
            source="telegram_text",
        )
        compare = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="bandingkan minggu ini dan minggu lalu",
            source="telegram_text",
        )

    assert spending.status == "spending_check"
    assert "Pengeluaran bulan ini" in spending.reply_text
    assert advice.status == "saving_advice"
    assert "Saran cepat" in advice.reply_text
    assert reason.status == "cashflow_reason"
    assert "Saldo cepat habis" in reason.reply_text
    assert health.status == "finance_health"
    assert "Selisih" in health.reply_text
    assert cutback.status == "cutback_advice"
    assert "Makanan" in cutback.reply_text
    assert compare.status == "week_compare"
    assert "Minggu ini" in compare.reply_text


def test_transaction_search_uses_local_history_without_llm(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_answer(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("LLM chat should not be called for transaction search")

    monkeypatch.setattr(
        "app.modules.transactions.service.answer_finance_question_with_llm",
        fail_answer,
    )

    with session_factory() as db:
        user = _create_user(db)
        food = db.scalar(select(Category).where(Category.name == "Makanan"))
        db.add(
            Transaction(
                user_id=user.id,
                type="expense",
                amount=Decimal("18000.00"),
                category_id=food.id if food else None,
                description="kopi susu",
                transaction_date=date.today(),
                source="telegram_text",
            )
        )
        db.commit()

        result = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="cari kopi",
            source="telegram_text",
        )

    assert result.status == "transaction_search"
    assert "kopi susu" in result.reply_text
    assert "Rp18.000" in result.reply_text


def test_latest_expense_list_uses_created_order_for_new_receipt(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        user = _create_user(db)
        food = db.scalar(select(Category).where(Category.name == "Makanan"))
        tagihan = db.scalar(select(Category).where(Category.name == "Tagihan"))
        db.add(
            Transaction(
                user_id=user.id,
                type="expense",
                amount=Decimal("5000.00"),
                category_id=food.id if food else None,
                description="jajan hari ini",
                transaction_date=date.today(),
                source="telegram_text",
            )
        )
        db.flush()
        db.add(
            Transaction(
                user_id=user.id,
                type="expense",
                amount=Decimal("140070.00"),
                category_id=tagihan.id if tagihan else None,
                description="Bayar wifi",
                transaction_date=date.today() - timedelta(days=4),
                source="receipt_ocr",
            )
        )
        db.commit()

        result = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="/pengeluaran",
            source="whatsapp_text",
        )

    assert result.status == "list_expense"
    assert result.reply_text.splitlines()[2].endswith("Bayar wifi")


def test_print_journal_is_saved_and_listed_as_education_expense(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        user = _create_user(db)
        saved = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="Saya print jurnal 15 k",
            source="whatsapp_text",
        )

        transaction = db.get(Transaction, saved.transaction_id)
        assert saved.status == "saved"
        assert transaction is not None
        assert transaction.amount == Decimal("15000.00")
        assert transaction.status == "confirmed"
        assert transaction.category is not None
        assert transaction.category.name == "Pendidikan"

        listed = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="list pengeluaran saya",
            source="whatsapp_text",
        )

    assert listed.status == "list_expense"
    assert "print jurnal" in listed.reply_text
    assert "Pendidikan" in listed.reply_text


def test_pending_ocr_receipt_is_not_listed_before_confirmation(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        user = _create_user(db)
        media = MediaFile(
            user_id=user.id,
            file_type="receipt",
            original_filename="transfer.jpg",
            stored_path="receipts/transfer.jpg",
            mime_type="image/jpeg",
            source="whatsapp_receipt",
        )
        db.add(media)
        db.flush()
        db.add(
            Receipt(
                user_id=user.id,
                media_file_id=media.id,
                merchant_name=None,
                total_amount=Decimal("50000.00"),
                status="needs_confirmation",
            )
        )
        db.commit()

        result = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="list pengeluaran",
            source="whatsapp_text",
        )

    assert result.status == "list_expense"
    assert "Rp50.000" not in result.reply_text


def test_expense_list_uses_current_user_id(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        user_a = _create_user(db, email="a@example.com")
        user_b = _create_user(db, email="b@example.com")
        food = db.scalar(select(Category).where(Category.name == "Makanan"))
        db.add_all(
            [
                Transaction(
                    user_id=user_a.id,
                    type="expense",
                    amount=Decimal("10000.00"),
                    category_id=food.id if food else None,
                    description="kopi user a",
                    transaction_date=date.today(),
                    source="whatsapp_text",
                    status="confirmed",
                ),
                Transaction(
                    user_id=user_b.id,
                    type="expense",
                    amount=Decimal("99000.00"),
                    category_id=food.id if food else None,
                    description="kopi user b",
                    transaction_date=date.today(),
                    source="whatsapp_text",
                    status="confirmed",
                ),
            ]
        )
        db.commit()

        result = handle_text_transaction(
            db=db,
            user_id=user_a.id,
            text="/pengeluaran",
            source="whatsapp_text",
        )

    assert "kopi user a" in result.reply_text
    assert "kopi user b" not in result.reply_text


def test_success_reply_only_after_database_commit(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with session_factory() as db:
        user = _create_user(db)

        def fail_commit() -> None:
            raise SQLAlchemyError("commit failed")

        monkeypatch.setattr(db, "commit", fail_commit)
        result = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="Beli makan 5k",
            source="whatsapp_text",
        )

        assert result.status == "save_failed"
        assert result.transaction_id is None
        assert "Tercatat" not in result.reply_text


def test_create_category_requires_confirmation_and_saves(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        user = _create_user(db)
        requested = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="buatkan saya kategori untuk tugas kuliah",
            source="whatsapp_text",
        )
        confirmed = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="YA",
            source="whatsapp_text",
        )
        category = db.scalar(
            select(Category).where(
                Category.name == "Tugas Kuliah",
                Category.type == "expense",
            )
        )

    assert requested.status == "category_create_needs_confirmation"
    assert confirmed.status == "category_created"
    assert category is not None


def test_reset_expense_requires_confirmation(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        user = _create_user(db)
        food = db.scalar(select(Category).where(Category.name == "Makanan"))
        income = db.scalar(select(Category).where(Category.name == "Gaji"))
        db.add_all(
            [
                Transaction(
                    user_id=user.id,
                    type="expense",
                    amount=Decimal("18000.00"),
                    category_id=food.id if food else None,
                    description="kopi",
                    transaction_date=date.today(),
                    source="telegram_text",
                ),
                Transaction(
                    user_id=user.id,
                    type="income",
                    amount=Decimal("100000.00"),
                    category_id=income.id if income else None,
                    description="gaji",
                    transaction_date=date.today(),
                    source="telegram_text",
                ),
            ]
        )
        db.commit()

        requested = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="kosongkan pengeluaran",
            source="telegram_text",
        )
        db.commit()
        assert requested.status == "reset_needs_confirmation"
        assert "YA RESET" in requested.reply_text
        assert len(db.scalars(select(Transaction)).all()) == 2

        confirmed = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="YA RESET",
            source="telegram_text",
        )
        db.commit()

        remaining = db.scalars(select(Transaction)).all()
        assert confirmed.status == "reset_done"
        assert "1 transaksi pengeluaran" in confirmed.reply_text
        assert len(remaining) == 1
        assert remaining[0].type == "income"


def test_reset_income_and_expense_can_be_cancelled_or_confirmed(
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as db:
        user = _create_user(db)
        food = db.scalar(select(Category).where(Category.name == "Makanan"))
        income = db.scalar(select(Category).where(Category.name == "Gaji"))
        db.add_all(
            [
                Transaction(
                    user_id=user.id,
                    type="expense",
                    amount=Decimal("18000.00"),
                    category_id=food.id if food else None,
                    description="kopi",
                    transaction_date=date.today(),
                    source="telegram_text",
                ),
                Transaction(
                    user_id=user.id,
                    type="income",
                    amount=Decimal("100000.00"),
                    category_id=income.id if income else None,
                    description="gaji",
                    transaction_date=date.today(),
                    source="telegram_text",
                ),
            ]
        )
        db.commit()

        requested = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="reset pengeluaran dan pemasukan",
            source="whatsapp_text",
        )
        cancelled = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="batal",
            source="whatsapp_text",
        )
        db.commit()
        assert requested.status == "reset_needs_confirmation"
        assert cancelled.status == "reset_cancelled"
        assert len(db.scalars(select(Transaction)).all()) == 2

        handle_text_transaction(
            db=db,
            user_id=user.id,
            text="hapus semua transaksi",
            source="whatsapp_text",
        )
        confirmed = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="YA RESET",
            source="whatsapp_text",
        )
        db.commit()

        assert confirmed.status == "reset_done"
        assert db.scalars(select(Transaction)).all() == []


def test_profile_and_purchase_questions_get_direct_replies(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_answer(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("LLM chat should not be needed for direct bot/profile replies")

    monkeypatch.setattr(
        "app.modules.transactions.service.answer_finance_question_with_llm",
        fail_answer,
    )

    with session_factory() as db:
        user = _create_user(db)
        food = db.scalar(select(Category).where(Category.name == "Makanan"))
        db.add(
            Transaction(
                user_id=user.id,
                type="expense",
                amount=Decimal("18000.00"),
                category_id=food.id if food else None,
                description="kopi susu",
                transaction_date=date.today(),
                source="telegram_text",
            )
        )
        db.commit()

        identity = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="hallo kamu siapa?",
            source="telegram_text",
        )
        purchases = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="bulan ini aku beli apa saja",
            source="telegram_text",
        )
        capability = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="kamu bisa bantu saya apa saja?",
            source="telegram_text",
        )

    assert identity.status == "bot_profile"
    assert "Aku Sakoo" in identity.reply_text
    assert purchases.status == "purchase_list"
    assert "kopi susu" in purchases.reply_text
    assert "Rp18.000" in purchases.reply_text
    assert capability.status == "bot_profile"
    assert "catat transaksi" in capability.reply_text


def test_income_source_question_handles_typo_without_llm(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_answer(*_args: object, **_kwargs: object) -> str:
        raise AssertionError("LLM chat should not be called for income source question")

    monkeypatch.setattr(
        "app.modules.transactions.service.answer_finance_question_with_llm",
        fail_answer,
    )

    with session_factory() as db:
        user = _create_user(db)
        gaji = db.scalar(select(Category).where(Category.name == "Gaji"))
        db.add(
            Transaction(
                user_id=user.id,
                type="income",
                amount=Decimal("200000.00"),
                category_id=gaji.id if gaji else None,
                description="gaji",
                transaction_date=date.today(),
                source="telegram_text",
            )
        )
        db.commit()

        result = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="pemsukan saya dari mana",
            source="telegram_text",
        )

    assert result.status == "income_source"
    assert "Pemasukan bulan ini dari" in result.reply_text
    assert "Gaji" in result.reply_text


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
        assert "Tercatat" in saved.reply_text


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
            text="menurutmu strategi keuangan terbaik buatku apa?",
            source="telegram_text",
        )

    assert result.status == "finance_chat"
    assert "pengeluaranmu" in result.reply_text
    assert calls and "Pengeluaran bulan ini" in str(calls[0]["context"])


def test_unknown_non_finance_question_falls_back_to_llm(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def mock_answer(*_args: object, **_kwargs: object) -> str:
        return "Aku asisten keuangan. Coba tanya soal keuanganmu ya!"

    monkeypatch.setattr(
        "app.modules.transactions.service.answer_finance_question_with_llm",
        mock_answer,
    )

    with session_factory() as db:
        user = _create_user(db)
        result = handle_text_transaction(
            db=db,
            user_id=user.id,
            text="ceritakan cuaca bandung",
            source="telegram_text",
        )

    assert result.status == "finance_chat"
    assert "keuangan" in result.reply_text.lower()


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


def _create_user(db: Session, *, email: str = "conversation@example.com") -> User:
    user = User(
        name="Conversation User",
        email=email,
        password_hash="hashed-password",
    )
    db.add(user)
    db.flush()
    return user
