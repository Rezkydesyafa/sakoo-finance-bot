from __future__ import annotations

import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent if (BACKEND_DIR.parent / ".env").exists() else BACKEND_DIR
sys.path.insert(0, str(BACKEND_DIR))

from app.modules.reports.pdf_template import render_report_pdf_html
from app.modules.reports.schemas import (
    ReportCategoryItem,
    ReportCategoryResponse,
    ReportSummaryResponse,
    ReportTransactionItem,
)


OUTPUT_DIR = PROJECT_DIR / "output" / "pdf"
HTML_OUTPUT = OUTPUT_DIR / "sakoo_ai_laporan_keuangan_bw.html"
PDF_OUTPUT = OUTPUT_DIR / "sakoo_ai_laporan_keuangan_bw.pdf"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    html = render_report_pdf_html(
        user_name="Rezky",
        summary=_sample_summary(),
        expense_categories=_sample_expense_categories(),
        income_categories=_sample_income_categories(),
        generated_at=datetime(2026, 6, 29, 9, 30),
    )
    HTML_OUTPUT.write_text(html, encoding="utf-8")
    print(f"Wrote {HTML_OUTPUT}")

    try:
        from weasyprint import HTML

        HTML(string=html, base_url=str(PROJECT_DIR)).write_pdf(str(PDF_OUTPUT))
    except Exception as exc:
        print(f"Skipped PDF render because WeasyPrint is unavailable: {exc}")
        return

    print(f"Wrote {PDF_OUTPUT}")


def _sample_summary() -> ReportSummaryResponse:
    transactions = [
        _transaction(1, "income", "500000", "Gaji", "saldo masuk", date(2026, 6, 29)),
        _transaction(2, "expense", "15000", "Makanan", "beli kopi", date(2026, 6, 29)),
        _transaction(3, "expense", "5000", "Makanan", "beli es teh", date(2026, 6, 28)),
        _transaction(4, "expense", "10000", "Belanja", "beli ice cream", date(2026, 6, 28)),
        _transaction(5, "income", "200000", "Gaji", "transfer masuk", date(2026, 6, 28)),
        _transaction(6, "expense", "10000", "Belanja", "beli seblak", date(2026, 6, 28)),
        _transaction(7, "expense", "15000", "Makanan", "makan mie ayam", date(2026, 6, 28)),
    ]
    return ReportSummaryResponse(
        report_type="month",
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        total_income=Decimal("700000"),
        total_expense=Decimal("55000"),
        net_balance=Decimal("645000"),
        transaction_count=7,
        income_count=2,
        expense_count=5,
        transactions=transactions,
        total_transactions=7,
        limit=100,
        offset=0,
        has_next=False,
    )


def _sample_expense_categories() -> ReportCategoryResponse:
    return ReportCategoryResponse(
        report_type="month",
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        type="expense",
        total_amount=Decimal("55000"),
        items=[
            ReportCategoryItem(
                category_id=1,
                category_name="Makanan",
                type="expense",
                total_amount=Decimal("35000"),
                transaction_count=3,
                percentage=Decimal("63.64"),
            ),
            ReportCategoryItem(
                category_id=2,
                category_name="Belanja",
                type="expense",
                total_amount=Decimal("20000"),
                transaction_count=2,
                percentage=Decimal("36.36"),
            ),
        ],
    )


def _sample_income_categories() -> ReportCategoryResponse:
    return ReportCategoryResponse(
        report_type="month",
        period_start=date(2026, 6, 1),
        period_end=date(2026, 6, 30),
        type="income",
        total_amount=Decimal("700000"),
        items=[
            ReportCategoryItem(
                category_id=3,
                category_name="Gaji",
                type="income",
                total_amount=Decimal("700000"),
                transaction_count=2,
                percentage=Decimal("100"),
            )
        ],
    )


def _transaction(
    transaction_id: int,
    transaction_type: str,
    amount: str,
    category_name: str,
    description: str,
    transaction_date: date,
) -> ReportTransactionItem:
    return ReportTransactionItem(
        id=transaction_id,
        type=transaction_type,
        amount=Decimal(amount),
        category_id=transaction_id,
        category_name=category_name,
        description=description,
        transaction_date=transaction_date,
        source="telegram_text",
    )


if __name__ == "__main__":
    main()
