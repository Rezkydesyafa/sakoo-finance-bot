from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Transaction


def find_category(
    *,
    db: Session,
    category_name: str | None,
    transaction_type: str | None,
) -> Category | None:
    if not transaction_type:
        return None

    names_to_try = [category_name, "Lainnya"]
    if transaction_type == "income":
        names_to_try.append("Gaji")

    for name in [item for item in names_to_try if item]:
        category = db.scalar(
            select(Category).where(
                func.lower(Category.name) == name.lower(),
                Category.type == transaction_type,
            )
        )
        if category:
            return category

    return None


def sum_transactions(
    db: Session,
    user_id: int,
    *,
    transaction_type: str,
    start_date: date | None = None,
    end_date: date | None = None,
) -> Decimal:
    query = select(func.coalesce(func.sum(Transaction.amount), 0)).where(
        Transaction.user_id == user_id,
        Transaction.type == transaction_type,
    )
    if start_date is not None:
        query = query.where(Transaction.transaction_date >= start_date)
    if end_date is not None:
        query = query.where(Transaction.transaction_date <= end_date)
    value = db.scalar(query)
    return Decimal(str(value or 0))


def calculate_balance(db: Session, user_id: int) -> Decimal:
    income_total = sum_transactions(db, user_id, transaction_type="income")
    expense_total = sum_transactions(db, user_id, transaction_type="expense")
    return income_total - expense_total


def list_transactions(
    db: Session,
    user_id: int,
    *,
    transaction_type: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 5,
    newest_by_created: bool = False,
) -> list[Transaction]:
    query = select(Transaction).where(Transaction.user_id == user_id)
    if transaction_type is not None:
        query = query.where(Transaction.type == transaction_type)
    if start_date is not None:
        query = query.where(Transaction.transaction_date >= start_date)
    if end_date is not None:
        query = query.where(Transaction.transaction_date <= end_date)
    order_by = (
        (Transaction.created_at.desc(), Transaction.id.desc())
        if newest_by_created
        else (Transaction.transaction_date.desc(), Transaction.id.desc())
    )
    return list(db.scalars(query.order_by(*order_by).limit(limit)))


def count_user_category_transactions(
    db: Session,
    user_id: int,
    category_id: int,
) -> int:
    value = db.scalar(
        select(func.count(Transaction.id)).where(
            Transaction.user_id == user_id,
            Transaction.category_id == category_id,
        )
    )
    return int(value or 0)


def top_expense_category(
    db: Session,
    user_id: int,
    *,
    start_date: date | None,
    end_date: date | None,
) -> tuple[str, Decimal] | None:
    query = (
        select(Category.name, func.coalesce(func.sum(Transaction.amount), 0).label("total"))
        .join(Category, Transaction.category_id == Category.id, isouter=True)
        .where(Transaction.user_id == user_id, Transaction.type == "expense")
        .group_by(Category.name)
        .order_by(func.coalesce(func.sum(Transaction.amount), 0).desc())
    )
    if start_date is not None:
        query = query.where(Transaction.transaction_date >= start_date)
    if end_date is not None:
        query = query.where(Transaction.transaction_date <= end_date)
    row = db.execute(query.limit(1)).first()
    if row is None:
        return None
    return row[0] or "Tanpa kategori", Decimal(str(row[1] or 0))


def sum_category_expense(
    db: Session,
    user_id: int,
    *,
    category_name: str,
    start_date: date,
    end_date: date,
) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .join(Category, Transaction.category_id == Category.id)
        .where(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            func.lower(Category.name) == category_name.lower(),
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
        )
    )
    return Decimal(str(value or 0))
