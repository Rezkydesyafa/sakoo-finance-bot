from datetime import date
from decimal import Decimal

from app.modules.parser.transaction_text import parse_transaction_text


def test_parser_reads_relative_dates_and_transaction_type_rules() -> None:
    today = date(2026, 6, 27)

    today_result = parse_transaction_text("beli makan 20 ribu hari ini", today=today)
    assert today_result.intent == "add_transaction"
    assert today_result.type == "expense"
    assert today_result.transaction_date == today
    assert today_result.amount == Decimal("20000")
    assert today_result.category == "Makanan"

    yesterday_result = parse_transaction_text(
        "bayar bensin 30rb kemarin",
        today=today,
    )
    assert yesterday_result.type == "expense"
    assert yesterday_result.transaction_date == date(2026, 6, 26)
    assert yesterday_result.amount == Decimal("30000")
    assert yesterday_result.category == "Transportasi"

    income_result = parse_transaction_text("gaji masuk 2 juta", today=today)
    assert income_result.type == "income"
    assert income_result.transaction_date == today
    assert income_result.amount == Decimal("2000000")
    assert income_result.category == "Gaji"


def test_parser_reads_explicit_numeric_and_month_name_dates() -> None:
    today = date(2026, 6, 27)

    numeric_result = parse_transaction_text(
        "beli buku rp20.000 tanggal 26/06/2026",
        today=today,
    )
    assert numeric_result.type == "expense"
    assert numeric_result.transaction_date == date(2026, 6, 26)
    assert numeric_result.category == "Pendidikan"

    month_name_result = parse_transaction_text(
        "bayar listrik 100rb 25 juni 2026",
        today=today,
    )
    assert month_name_result.type == "expense"
    assert month_name_result.transaction_date == date(2026, 6, 25)
    assert month_name_result.category == "Tagihan"


def test_parser_detects_bot_command_intents() -> None:
    today = date(2026, 6, 27)

    report_result = parse_transaction_text("laporan bulan ini", today=today)
    assert report_result.intent == "get_report"
    assert report_result.period == "month"
    assert report_result.need_confirmation is False

    export_result = parse_transaction_text("export laporan bulan ini", today=today)
    assert export_result.intent == "export_pdf"
    assert export_result.period == "month"
    assert export_result.need_confirmation is False

    weekly_report = parse_transaction_text("laporan minggu ini", today=today)
    assert weekly_report.intent == "get_report"
    assert weekly_report.period == "week"

    recent_result = parse_transaction_text("riwayat transaksi", today=today)
    assert recent_result.intent == "recent_transactions"

    delete_result = parse_transaction_text("hapus transaksi terakhir", today=today)
    assert delete_result.intent == "delete_last_transaction"

    help_result = parse_transaction_text("bantuan", today=today)
    assert help_result.intent == "help"


def test_transaction_input_is_not_misclassified_as_command() -> None:
    today = date(2026, 6, 27)

    normal_transaction = parse_transaction_text("beli makan 20 ribu", today=today)
    assert normal_transaction.intent == "add_transaction"
    assert normal_transaction.type == "expense"

    transaction_with_report_word = parse_transaction_text(
        "beli buku laporan 20 ribu",
        today=today,
    )
    assert transaction_with_report_word.intent == "add_transaction"
    assert transaction_with_report_word.category == "Pendidikan"
