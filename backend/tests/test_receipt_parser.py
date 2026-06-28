from datetime import date
from decimal import Decimal

from app.modules.ocr.receipt_parser import parse_receipt_text


def test_receipt_parser_extracts_grand_total_merchant_and_date() -> None:
    result = parse_receipt_text(
        """
        TOKO SAKOO
        Jl. Mawar No. 10
        27/06/2026 14:20
        Kopi             Rp 12.000
        Roti             Rp 8.000
        GRAND TOTAL      Rp 20.000
        """,
    )

    assert result.total_amount == Decimal("20000.00")
    assert result.merchant_name == "TOKO SAKOO"
    assert result.receipt_date == date(2026, 6, 27)
    assert result.confidence >= Decimal("0.8500")
    assert result.status == "processed"
    assert result.need_confirmation is False


def test_receipt_parser_extracts_total_bayar_with_amount_on_next_line() -> None:
    result = parse_receipt_text(
        """
        SAKOO MART
        Tanggal 2026-06-27
        TOTAL BAYAR
        Rp20.000
        Tunai Rp50.000
        Kembali Rp30.000
        """,
    )

    assert result.total_amount == Decimal("20000.00")
    assert result.merchant_name == "SAKOO MART"
    assert result.receipt_date == date(2026, 6, 27)
    assert result.status == "processed"


def test_receipt_parser_requires_manual_input_when_total_keyword_missing() -> None:
    result = parse_receipt_text(
        """
        TOKO SAKOO
        Kopi Rp 12.000
        Roti Rp 8.000
        Tunai Rp 20.000
        """,
    )

    assert result.total_amount is None
    assert result.merchant_name == "TOKO SAKOO"
    assert result.status == "manual_input_required"
    assert result.need_confirmation is True
    assert "missing_total_keyword" in result.reasons
    assert "ambiguous_amounts_without_total_keyword" in result.reasons


def test_receipt_parser_marks_different_total_candidates_for_confirmation() -> None:
    result = parse_receipt_text(
        """
        TOKO SAKOO
        TOTAL BAYAR Rp 20.000
        TOTAL PEMBAYARAN Rp 21.000
        """,
    )

    assert result.total_amount == Decimal("21000.00")
    assert result.status == "needs_confirmation"
    assert result.need_confirmation is True
    assert "multiple_total_candidates" in result.reasons
