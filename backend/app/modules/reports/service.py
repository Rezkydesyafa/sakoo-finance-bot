from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import Select, case, func, select
from sqlalchemy.orm import Session

from app.models import Category, Transaction
from app.modules.reports.period import ReportPeriod
from app.modules.reports.schemas import (
    ReportCategoryItem,
    ReportCategoryResponse,
    ReportSummaryResponse,
    ReportTransactionItem,
)
from app.modules.transactions.query import (
    TransactionQueryFilters,
    build_transactions_query,
    query_transactions,
)


ZERO = Decimal("0.00")


@dataclass(frozen=True)
class ReportFilters:
    user_id: int
    report_period: ReportPeriod
    limit: int = 100
    offset: int = 0


def build_report_summary(db: Session, filters: ReportFilters) -> ReportSummaryResponse:
    totals = _query_report_totals(
        db,
        user_id=filters.user_id,
        period_start=filters.report_period.period_start,
        period_end=filters.report_period.period_end,
    )
    query_result = query_transactions(
        db,
        TransactionQueryFilters(
            user_id=filters.user_id,
            start_date=filters.report_period.period_start,
            end_date=filters.report_period.period_end,
            limit=filters.limit,
            offset=filters.offset,
        ),
    )

    return ReportSummaryResponse(
        report_type=filters.report_period.report_type,
        period_start=filters.report_period.period_start,
        period_end=filters.report_period.period_end,
        total_income=totals.total_income,
        total_expense=totals.total_expense,
        net_balance=totals.total_income - totals.total_expense,
        transaction_count=totals.transaction_count,
        income_count=totals.income_count,
        expense_count=totals.expense_count,
        transactions=[_to_report_transaction_item(item) for item in query_result.items],
        total_transactions=query_result.total,
        limit=query_result.limit,
        offset=query_result.offset,
        has_next=query_result.has_next,
    )


def build_report_category(
    db: Session,
    *,
    user_id: int,
    report_period: ReportPeriod,
    transaction_type: str | None = None,
) -> ReportCategoryResponse:
    statement = _base_period_query(
        user_id=user_id,
        period_start=report_period.period_start,
        period_end=report_period.period_end,
    )
    if transaction_type is not None:
        statement = statement.where(Transaction.type == transaction_type)

    rows = db.execute(
        statement.with_only_columns(
            Transaction.category_id,
            func.coalesce(Category.name, "Tanpa kategori").label("category_name"),
            Transaction.type,
            func.coalesce(func.sum(Transaction.amount), 0).label("total_amount"),
            func.count(Transaction.id).label("transaction_count"),
        )
        .select_from(Transaction)
        .join(Category, Category.id == Transaction.category_id, isouter=True)
        .group_by(Transaction.category_id, Category.name, Transaction.type)
        .order_by(func.sum(Transaction.amount).desc(), Category.name.asc())
    ).all()

    total_amount = sum((_to_decimal(row.total_amount) for row in rows), ZERO)
    items = [
        ReportCategoryItem(
            category_id=row.category_id,
            category_name=row.category_name,
            type=row.type,
            total_amount=_to_decimal(row.total_amount),
            transaction_count=int(row.transaction_count or 0),
            percentage=_calculate_percentage(_to_decimal(row.total_amount), total_amount),
        )
        for row in rows
    ]

    return ReportCategoryResponse(
        report_type=report_period.report_type,
        period_start=report_period.period_start,
        period_end=report_period.period_end,
        type=transaction_type,
        total_amount=total_amount,
        items=items,
    )


@dataclass(frozen=True)
class ReportTotals:
    total_income: Decimal
    total_expense: Decimal
    transaction_count: int
    income_count: int
    expense_count: int


def _query_report_totals(
    db: Session,
    *,
    user_id: int,
    period_start: date,
    period_end: date,
) -> ReportTotals:
    statement = _base_period_query(
        user_id=user_id,
        period_start=period_start,
        period_end=period_end,
    ).with_only_columns(
        func.coalesce(
            func.sum(case((Transaction.type == "income", Transaction.amount), else_=0)),
            0,
        ).label("total_income"),
        func.coalesce(
            func.sum(case((Transaction.type == "expense", Transaction.amount), else_=0)),
            0,
        ).label("total_expense"),
        func.count(Transaction.id).label("transaction_count"),
        func.coalesce(
            func.sum(case((Transaction.type == "income", 1), else_=0)),
            0,
        ).label("income_count"),
        func.coalesce(
            func.sum(case((Transaction.type == "expense", 1), else_=0)),
            0,
        ).label("expense_count"),
    )
    row = db.execute(statement).one()
    return ReportTotals(
        total_income=_to_decimal(row.total_income),
        total_expense=_to_decimal(row.total_expense),
        transaction_count=int(row.transaction_count or 0),
        income_count=int(row.income_count or 0),
        expense_count=int(row.expense_count or 0),
    )


def _base_period_query(
    *,
    user_id: int,
    period_start: date,
    period_end: date,
) -> Select[tuple[Transaction]]:
    return build_transactions_query(
        TransactionQueryFilters(
            user_id=user_id,
            start_date=period_start,
            end_date=period_end,
        )
    )


def _to_report_transaction_item(transaction: Transaction) -> ReportTransactionItem:
    return ReportTransactionItem(
        id=transaction.id,
        type=transaction.type,
        amount=transaction.amount,
        category_id=transaction.category_id,
        category_name=transaction.category.name if transaction.category else None,
        description=transaction.description,
        transaction_date=transaction.transaction_date,
        source=transaction.source,
    )


def _to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value or "0")).quantize(Decimal("0.01"))


def _calculate_percentage(amount: Decimal, total_amount: Decimal) -> Decimal:
    if total_amount <= 0:
        return ZERO
    percentage = (amount / total_amount * Decimal("100")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    return percentage
