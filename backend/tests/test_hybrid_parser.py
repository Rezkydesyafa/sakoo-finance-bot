from datetime import date
from decimal import Decimal

from app.modules.parser.amount_parser import parse_amount
from app.modules.parser.intent_router import detect_intent
from app.modules.parser.normalizer import normalize_text
from app.modules.parser.service import parse_message
from app.modules.parser.transaction_parser import parse_transaction_text


def test_normalizer_handles_slang_and_compact_amounts() -> None:
    assert normalize_text("  Dapet   uang saku 100k ") == "dapat uang saku 100000"
    assert normalize_text("bayar bensin 30rb") == "bayar bensin 30000"
    assert normalize_text("gaji masuk 2 jt") == "gaji masuk 2000000"
    assert normalize_text("Rp20.000") == "20000"


def test_amount_parser_reads_common_student_chat_amounts() -> None:
    assert parse_amount("jajan kopi 18k") == Decimal("18000")
    assert parse_amount("bayar bensin 30rb") == Decimal("30000")
    assert parse_amount("beli makan 20 ribu") == Decimal("20000")
    assert parse_amount("gaji masuk 2 juta") == Decimal("2000000")
    assert parse_amount("Rp20.000") == Decimal("20000")


def test_intent_router_keeps_commands_out_of_transaction_parser() -> None:
    assert detect_intent("saldo saya berapa").intent == "get_balance"
    assert detect_intent("/saldo").intent == "get_balance"
    assert detect_intent("/start").intent == "help"
    assert detect_intent("list pengeluaran").intent == "list_expense"
    assert detect_intent("list pemasukan").intent == "list_income"
    assert detect_intent("laporan bulan ini").intent == "get_report"
    assert detect_intent("export laporan bulan ini").intent == "export_pdf"
    assert detect_intent("download laporan bulan ini").intent == "export_pdf"
    assert detect_intent("beli makan").intent == "add_transaction"


def test_transaction_parser_understands_casual_income_and_expense() -> None:
    today = date(2026, 6, 29)

    coffee = parse_transaction_text("jajan kopi 18k", today=today)
    assert coffee.intent == "add_transaction"
    assert coffee.type == "expense"
    assert coffee.amount == Decimal("18000")
    assert coffee.category == "Makanan"

    fuel = parse_transaction_text("bayar bensin 30rb", today=today)
    assert fuel.type == "expense"
    assert fuel.amount == Decimal("30000")
    assert fuel.category == "Transportasi"

    allowance = parse_transaction_text("dapet uang saku 100k", today=today)
    assert allowance.type == "income"
    assert allowance.amount == Decimal("100000")
    assert allowance.category == "Uang Saku"
    assert allowance.need_confirmation is False

    casual_allowance = parse_transaction_text("uang jajan nyokap 200rb", today=today)
    assert casual_allowance.type == "income"
    assert casual_allowance.amount == Decimal("200000")
    assert casual_allowance.category == "Uang Saku"


def test_parse_message_marks_unknown_and_missing_amount_without_llm() -> None:
    balance = parse_message(
        "saldo saya berapa",
        source="telegram_text",
        today=date(2026, 6, 29),
    )
    assert balance.intent == "get_balance"
    assert balance.amount is None
    assert balance.need_confirmation is False

    missing_amount = parse_message(
        "beli makan",
        source="telegram_text",
        today=date(2026, 6, 29),
    )
    assert missing_amount.intent == "add_transaction"
    assert missing_amount.amount is None
    assert missing_amount.need_confirmation is True
    assert "missing_amount" in missing_amount.reasons
