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
os.environ["BOT_REPLY_STYLE"] = "friendly"

from app.config import get_settings
from app.database import Base
from app.models import Category, Transaction, User
from app.modules.transactions.service import handle_text_transaction


YOUTH_MESSAGES = [
    (1, "beli kopi 18 ribu"),
    (2, "gw beli es jeruk 5k"),
    (3, "tadi jajan seblak 12rb"),
    (4, "bayar wifi 140.070"),
    (5, "beli makan 25k"),
    (6, "parkir kampus 5 ribu"),
    (7, "gojek ke kampus 18k"),
    (8, "beli paket data 50rb"),
    (9, "bayar kos 850 ribu"),
    (10, "beli baju thrift 75k"),
    (11, "top up game 30rb"),
    (12, "beli skincare 120k"),
    (13, "print jurnal 15 k"),
    (14, "fotokopi tugas 7rb"),
    (15, "beli buku kuliah 95 ribu"),
    (16, "gajian 2 juta"),
    (17, "masuk uang freelance 350k"),
    (18, "dikasih mama 100 ribu"),
    (19, "refund shopee 45rb"),
    (20, "pemasukan dari jual hoodie 180k"),
    (21, "transfer masuk 500rb"),
    (22, "uang jajan bulan ini 1.2jt"),
    (23, "td gw beli kopi 18k"),
    (24, "aku abis makan 23000"),
    (25, "brusan bayar grab 17rb"),
    (26, "kmrn beli ayam geprek 15k"),
    (27, "pngeluaran 20rb buat es kopi"),
    (28, "msuk uang 100k dari temen"),
    (29, "beli pulsa lima puluh ribu"),
    (30, "jajan cilok sepuluh ribu"),
    (31, "kemarin beli kopi 18k"),
    (32, "tadi malam beli makan 30rb"),
    (33, "minggu lalu bayar bensin 35k"),
    (34, "tanggal 2 bayar wifi 140070"),
    (35, "1 juli beli buku kuliah 90rb"),
    (36, "bulan lalu bayar kos 800rb"),
    (37, "ya"),
    (38, "YA"),
    (39, "iya simpan"),
    (40, "oke catat"),
    (41, "jangan simpan"),
    (42, "batal"),
    (43, "edit total 50000"),
    (44, "edit tanggal kemarin"),
    (45, "edit kategori makanan"),
    (46, "edit catatan bayar wifi bulanan"),
    (47, "edit merchant indomaret"),
    (48, "salah, totalnya 15rb"),
    (49, "list pengeluaran"),
    (50, "pengeluaran terbaru"),
    (51, "riwayat transaksi"),
    (52, "bulan ini aku beli apa aja?"),
    (53, "transaksi terakhir apa?"),
    (54, "pemasukan saya dari mana?"),
    (55, "list pemasukan bulan ini"),
    (56, "cari kopi"),
    (57, "cari gojek bulan ini"),
    (58, "cari pengeluaran kampus"),
    (59, "cari transaksi wifi"),
    (60, "sisa saldo saya berapa?"),
    (61, "saldo aku sekarang?"),
    (62, "bulan ini aku boros gak?"),
    (63, "makanan bulan ini habis berapa?"),
    (64, "budget makan tinggal berapa?"),
    (65, "apa yang harus aku kurangi?"),
    (66, "kenapa saldo aku minus?"),
    (67, "bulan ini aman gak?"),
    (68, "bandingkan minggu ini dan minggu lalu"),
    (69, "kategori paling boros apa?"),
    (70, "pengeluaran hari ini berapa?"),
    (71, "buatkan kategori tugas kuliah"),
    (72, "bikin kategori nongkrong"),
    (73, "tambah kategori pacaran"),
    (74, "kategori print jurnal masuk mana?"),
    (75, "ganti kategori transaksi terakhir jadi pendidikan"),
    (76, "pengeluaran kuliah bulan ini berapa?"),
    (77, "aku sering keluar uang buat apa?"),
    (78, "kosongkan pengeluaran"),
    (79, "reset pemasukan"),
    (80, "reset semua transaksi"),
    (81, "hapus transaksi terakhir"),
    (82, "batal hapus"),
    (83, "ya reset"),
    (84, "kamu bisa bantu apa?"),
    (85, "bantu aku atur uang bulan ini"),
    (86, "kasih saran biar ga boros"),
    (87, "aku cuma punya 100rb sampai minggu depan, gimana?"),
    (88, "mending beli kopi tiap hari atau hemat?"),
    (89, "bikin rencana hemat anak kos"),
    (90, "aku pengen nabung 500rb bulan ini, bisa ga?"),
    (91, "gimana cara ngurangin jajan?"),
    (92, "kasih evaluasi keuangan aku"),
    (93, "aku harus stop langganan apa?"),
    (94, "menurutmu pengeluaran aku sehat gak?"),
    (95, "kopi 18"),
    (96, "15k"),
    (97, "bayar"),
    (98, "makan"),
    (99, "aku abis keluar uang"),
    (100, "ini mahal gak?"),
    (101, "catat yang tadi"),
    (102, "uangku habis"),
    (103, "aku lupa nominalnya"),
    (104, "tadi bayar dua kali"),
    (105, "salah catat dong"),
]


def expected_case(
    number: int,
    text: str,
    statuses: tuple[str, ...],
    *,
    transaction_type: str | None = None,
    xfail: str | None = None,
):
    marks = [pytest.mark.xfail(reason=xfail)] if xfail else []
    return pytest.param(number, text, statuses, transaction_type, id=f"{number:03d}", marks=marks)


EXPECTED_CASES = [
    expected_case(1, "beli kopi 18 ribu", ("saved",), transaction_type="expense"),
    expected_case(13, "print jurnal 15 k", ("saved",), transaction_type="expense"),
    expected_case(16, "gajian 2 juta", ("saved",), transaction_type="income", xfail="income slang gajian belum terbaca"),
    expected_case(17, "masuk uang freelance 350k", ("saved",), transaction_type="income"),
    expected_case(18, "dikasih mama 100 ribu", ("saved",), transaction_type="income", xfail="income slang dikasih belum terbaca"),
    expected_case(19, "refund shopee 45rb", ("saved",), transaction_type="income", xfail="refund masih tercatat sebagai pengeluaran"),
    expected_case(28, "msuk uang 100k dari temen", ("saved",), transaction_type="income", xfail="typo msuk belum terbaca sebagai pemasukan"),
    expected_case(29, "beli pulsa lima puluh ribu", ("saved",), transaction_type="expense"),
    expected_case(49, "list pengeluaran", ("list_expense",)),
    expected_case(50, "pengeluaran terbaru", ("list_expense",), xfail="frasa pengeluaran terbaru belum route ke list"),
    expected_case(57, "cari gojek bulan ini", ("transaction_search",)),
    expected_case(58, "cari pengeluaran kampus", ("transaction_search",)),
    expected_case(59, "cari transaksi wifi", ("transaction_search",)),
    expected_case(64, "budget makan tinggal berapa?", ("budget_remaining",)),
    expected_case(65, "apa yang harus aku kurangi?", ("cutback_advice",), xfail="cutback intent belum tertangkap tanpa kata pengeluaran"),
    expected_case(74, "kategori print jurnal masuk mana?", ("category_lookup", "finance_chat"), xfail="kategori lookup kebaca add_transaction tanpa nominal"),
    expected_case(75, "ganti kategori transaksi terakhir jadi pendidikan", ("edit_last_transaction",), xfail="edit transaksi terakhir belum tersedia"),
    expected_case(76, "pengeluaran kuliah bulan ini berapa?", ("category_summary",), xfail="kuliah belum menjadi alias kategori Pendidikan"),
    expected_case(77, "aku sering keluar uang buat apa?", ("spending_analysis", "finance_chat"), xfail="analisis kebaca add_transaction tanpa nominal"),
    expected_case(84, "kamu bisa bantu apa?", ("bot_profile",)),
    expected_case(85, "bantu aku atur uang bulan ini", ("finance_chat", "saving_advice"), xfail="general finance advice masih unknown saat LLM off"),
    expected_case(86, "kasih saran biar ga boros", ("saving_advice",)),
    expected_case(87, "aku cuma punya 100rb sampai minggu depan, gimana?", ("limited_cash_plan",)),
    expected_case(88, "mending beli kopi tiap hari atau hemat?", ("finance_chat", "saving_advice"), xfail="pertanyaan pilihan hemat kebaca spending_check"),
    expected_case(89, "bikin rencana hemat anak kos", ("finance_chat", "saving_advice"), xfail="rencana hemat kebaca spending_check"),
    expected_case(90, "aku pengen nabung 500rb bulan ini, bisa ga?", ("finance_chat", "saving_goal"), xfail="target tabungan masih unknown"),
    expected_case(91, "gimana cara ngurangin jajan?", ("finance_chat", "saving_advice"), xfail="ngurangin jajan kebaca add_transaction tanpa nominal"),
    expected_case(92, "kasih evaluasi keuangan aku", ("finance_chat", "finance_health"), xfail="evaluasi keuangan masih unknown saat LLM off"),
    expected_case(93, "aku harus stop langganan apa?", ("finance_chat", "cutback_advice"), xfail="stop langganan kebaca add_transaction tanpa nominal"),
    expected_case(94, "menurutmu pengeluaran aku sehat gak?", ("finance_health",), xfail="frasa sehat pengeluaran belum route ke finance_health"),
    expected_case(95, "kopi 18", ("needs_confirmation",), xfail="nominal tanpa unit disimpan sebagai Rp18"),
    expected_case(96, "15k", ("needs_confirmation",), xfail="nominal saja belum minta konteks transaksi"),
    expected_case(97, "bayar", ("needs_confirmation",)),
    expected_case(98, "makan", ("needs_confirmation",)),
    expected_case(99, "aku abis keluar uang", ("needs_confirmation",)),
    expected_case(100, "ini mahal gak?", ("finance_chat",), xfail="pertanyaan umum mahal masih unknown"),
    expected_case(101, "catat yang tadi", ("needs_context", "finance_chat"), xfail="referensi yang tadi belum punya handler"),
    expected_case(102, "uangku habis", ("needs_confirmation", "finance_chat")),
    expected_case(103, "aku lupa nominalnya", ("needs_confirmation", "needs_context"), xfail="lupa nominal masih unknown"),
    expected_case(104, "tadi bayar dua kali", ("duplicate_check", "finance_chat"), xfail="duplikasi bayar kebaca transaksi tanpa nominal"),
    expected_case(105, "salah catat dong", ("needs_context", "finance_chat"), xfail="koreksi tanpa konteks masih unknown"),
]


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
                Category(name="Hiburan", type="expense"),
                Category(name="Kesehatan", type="expense"),
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


@pytest.mark.parametrize(("number", "text"), YOUTH_MESSAGES, ids=lambda item: str(item))
def test_youth_message_smoke_does_not_crash(
    session_factory: sessionmaker[Session],
    number: int,
    text: str,
) -> None:
    with session_factory() as db:
        user = _create_user(db, email=f"smoke-{number}@example.com")
        result = handle_text_transaction(db=db, user_id=user.id, text=text, source="whatsapp_text")

    assert result.status != "save_failed"
    assert result.reply_text.strip()


@pytest.mark.parametrize(("number", "text", "statuses", "transaction_type"), EXPECTED_CASES)
def test_youth_message_expected_outcomes(
    session_factory: sessionmaker[Session],
    number: int,
    text: str,
    statuses: tuple[str, ...],
    transaction_type: str | None,
) -> None:
    with session_factory() as db:
        user = _create_user(db, email=f"expect-{number}@example.com")
        _seed_user_transactions(db, user.id)
        result = handle_text_transaction(db=db, user_id=user.id, text=text, source="whatsapp_text")
        transaction = db.get(Transaction, result.transaction_id) if result.transaction_id else None

    assert result.status in statuses
    if transaction_type is not None:
        assert transaction is not None
        assert transaction.type == transaction_type


@pytest.mark.parametrize(
    ("reply", "expected_status"),
    [
        ("ya", "saved"),
        ("YA", "saved"),
        pytest.param("iya simpan", "saved", marks=pytest.mark.xfail(reason="multi-word yes belum cocok regex")),
        pytest.param("oke catat", "saved", marks=pytest.mark.xfail(reason="multi-word yes belum cocok regex")),
        pytest.param("jangan simpan", "cancelled", marks=pytest.mark.xfail(reason="jangan simpan belum dianggap cancel")),
        ("batal", "cancelled"),
        ("edit total 50000", "edit_updated"),
        ("edit tanggal kemarin", "edit_updated"),
        ("edit kategori makanan", "edit_updated"),
        ("edit catatan bayar wifi bulanan", "edit_updated"),
        ("edit merchant indomaret", "edit_updated"),
        pytest.param("salah, totalnya 15rb", "edit_updated", marks=pytest.mark.xfail(reason="koreksi natural total belum terbaca")),
    ],
)
def test_confirmation_text_with_pending_transaction(
    session_factory: sessionmaker[Session],
    reply: str,
    expected_status: str,
) -> None:
    with session_factory() as db:
        user = _create_user(db, email=f"pending-{reply}@example.com")
        first = handle_text_transaction(db=db, user_id=user.id, text="keluar 20 ribu", source="whatsapp_text")
        assert first.status == "needs_confirmation"

        result = handle_text_transaction(db=db, user_id=user.id, text=reply, source="whatsapp_text")

    assert result.status == expected_status


def test_ya_reset_confirms_pending_reset(session_factory: sessionmaker[Session]) -> None:
    with session_factory() as db:
        user = _create_user(db, email="reset@example.com")
        _seed_user_transactions(db, user.id)

        requested = handle_text_transaction(db=db, user_id=user.id, text="reset semua transaksi", source="whatsapp_text")
        confirmed = handle_text_transaction(db=db, user_id=user.id, text="ya reset", source="whatsapp_text")

    assert requested.status == "reset_needs_confirmation"
    assert confirmed.status == "reset_done"


def _seed_user_transactions(db: Session, user_id: int) -> None:
    food = db.scalar(select(Category).where(Category.name == "Makanan", Category.type == "expense"))
    transport = db.scalar(select(Category).where(Category.name == "Transportasi"))
    income = db.scalar(select(Category).where(Category.name == "Uang Saku"))
    db.add_all(
        [
            Transaction(
                user_id=user_id,
                type="expense",
                amount=Decimal("18000.00"),
                category_id=food.id if food else None,
                description="beli kopi",
                transaction_date=date(2026, 7, 7),
                source="whatsapp_text",
                status="confirmed",
            ),
            Transaction(
                user_id=user_id,
                type="expense",
                amount=Decimal("18000.00"),
                category_id=transport.id if transport else None,
                description="gojek ke kampus",
                transaction_date=date(2026, 7, 7),
                source="whatsapp_text",
                status="confirmed",
            ),
            Transaction(
                user_id=user_id,
                type="income",
                amount=Decimal("100000.00"),
                category_id=income.id if income else None,
                description="uang jajan",
                transaction_date=date(2026, 7, 7),
                source="whatsapp_text",
                status="confirmed",
            ),
        ]
    )
    db.commit()


def _create_user(db: Session, *, email: str) -> User:
    user = User(name="Youth Tester", email=email, password_hash="hashed-password")
    db.add(user)
    db.flush()
    return user
