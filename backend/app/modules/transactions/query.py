from dataclasses import dataclass
from datetime import date

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import Transaction

CONFIRMED_TRANSACTION_STATUS = "confirmed"


@dataclass(frozen=True)
class TransactionQueryFilters:
    user_id: int
    start_date: date | None = None
    end_date: date | None = None
    category_id: int | None = None
    type: str | None = None
    limit: int = 50
    offset: int = 0


@dataclass(frozen=True)
class TransactionQueryResult:
    items: list[Transaction]
    total: int
    limit: int
    offset: int

    @property
    def has_next(self) -> bool:
        return self.offset + len(self.items) < self.total


def query_transactions(db: Session, filters: TransactionQueryFilters) -> TransactionQueryResult:
    base_statement = build_transactions_query(filters)
    total = db.scalar(
        select(func.count()).select_from(base_statement.order_by(None).subquery())
    )
    items = list(
        db.scalars(
            base_statement
            .order_by(Transaction.created_at.desc(), Transaction.id.desc())
            .limit(filters.limit)
            .offset(filters.offset)
        )
    )

    return TransactionQueryResult(
        items=items,
        total=total or 0,
        limit=filters.limit,
        offset=filters.offset,
    )


def build_transactions_query(filters: TransactionQueryFilters) -> Select[tuple[Transaction]]:
    statement = select(Transaction).where(
        Transaction.user_id == filters.user_id,
        Transaction.status == CONFIRMED_TRANSACTION_STATUS,
    )

    if filters.start_date is not None:
        statement = statement.where(Transaction.transaction_date >= filters.start_date)
    if filters.end_date is not None:
        statement = statement.where(Transaction.transaction_date <= filters.end_date)
    if filters.category_id is not None:
        statement = statement.where(Transaction.category_id == filters.category_id)
    if filters.type is not None:
        statement = statement.where(Transaction.type == filters.type)

    return statement
