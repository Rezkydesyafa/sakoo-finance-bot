from datetime import date
from decimal import Decimal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Category, Transaction

CONFIRMED_TRANSACTION_STATUS = "confirmed"


def find_category(
    *,
    db: Session,
    category_name: str | None,
    transaction_type: str | None,
    user_id: int | None = None,
) -> Category | None:
    if not transaction_type:
        return None

    names_to_try = [category_name, "Lainnya"]
    if transaction_type == "income":
        names_to_try.append("Gaji")

    for name in [item for item in names_to_try if item]:
        # First try user-specific category, then default
        query = select(Category).where(
            func.lower(Category.name) == name.lower(),
            Category.type.in_([transaction_type, "both"]),
            Category.is_active == True,  # noqa: E712
        )
        if user_id is not None:
            # Prefer user's own category, fall back to default (user_id IS NULL)
            query = query.where(
                or_(Category.user_id == user_id, Category.user_id.is_(None))
            ).order_by(
                # user-specific first (non-null user_id)
                Category.user_id.is_(None).asc(),
            )
        else:
            query = query.where(Category.user_id.is_(None))

        category = db.scalar(query)
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
        Transaction.status == CONFIRMED_TRANSACTION_STATUS,
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
    limit: int = 10,
    newest_by_created: bool = False,
    sort_by_amount: bool = False,
    sort_order: str = "desc",
    category_name: str | None = None,
) -> list[Transaction]:
    query = select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.status == CONFIRMED_TRANSACTION_STATUS,
    )
    if transaction_type is not None:
        query = query.where(Transaction.type == transaction_type)
    if start_date is not None:
        query = query.where(Transaction.transaction_date >= start_date)
    if end_date is not None:
        query = query.where(Transaction.transaction_date <= end_date)
    if category_name is not None:
        query = query.join(Category, Transaction.category_id == Category.id).where(
            func.lower(Category.name) == category_name.lower()
        )

    if sort_by_amount:
        order_by = (
            (Transaction.amount.desc(), Transaction.id.desc())
            if sort_order == "desc"
            else (Transaction.amount.asc(), Transaction.id.asc())
        )
    elif newest_by_created:
        order_by = (Transaction.created_at.desc(), Transaction.id.desc())
    else:
        order_by = (Transaction.transaction_date.desc(), Transaction.id.desc())

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
            Transaction.status == CONFIRMED_TRANSACTION_STATUS,
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
        .where(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            Transaction.status == CONFIRMED_TRANSACTION_STATUS,
        )
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
            Transaction.status == CONFIRMED_TRANSACTION_STATUS,
            func.lower(Category.name) == category_name.lower(),
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
        )
    )
    return Decimal(str(value or 0))


def list_user_categories(
    db: Session,
    user_id: int,
    *,
    include_defaults: bool = True,
    active_only: bool = True,
) -> list[Category]:
    """List categories visible to a user (their own + defaults)."""
    conditions = []
    if include_defaults:
        conditions.append(
            or_(Category.user_id == user_id, Category.user_id.is_(None))
        )
    else:
        conditions.append(Category.user_id == user_id)
    if active_only:
        conditions.append(Category.is_active == True)  # noqa: E712

    return list(
        db.scalars(
            select(Category)
            .where(*conditions)
            .order_by(Category.is_default.desc(), Category.name.asc())
        )
    )


def detect_category_by_keywords(
    db: Session,
    user_id: int,
    text: str,
    *,
    transaction_type: str | None = None,
) -> Category | None:
    """Match text against category keywords from DB (user-specific + defaults)."""
    categories = list_user_categories(db, user_id)
    text_lower = text.lower()
    tokens = set(text_lower.split())

    best_match: Category | None = None
    best_score = 0

    for category in categories:
        if transaction_type and category.type not in {transaction_type, "both"}:
            continue
        keywords = category.keywords or []
        if not keywords:
            continue
        score = sum(
            1 for kw in keywords
            if kw in tokens or kw in text_lower
        )
        # Prefer user-specific over default on tie
        if score > best_score or (score == best_score and score > 0 and category.user_id is not None):
            best_match = category
            best_score = score

    return best_match if best_score > 0 else None
