from __future__ import annotations

from datetime import date
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import Category, Transaction


def list_categories(
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

    categories = list(
        db.scalars(
            select(Category)
            .where(*conditions)
            .order_by(Category.is_default.desc(), Category.name.asc())
        )
    )

    today = date.today()
    start_of_month = today.replace(day=1)

    sums = dict(
        db.execute(
            select(Transaction.category_id, func.sum(Transaction.amount))
            .where(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= start_of_month,
                Transaction.type == "expense"
            )
            .group_by(Transaction.category_id)
        ).all()
    )

    for cat in categories:
        cat.spent_this_month = float(sums.get(cat.id) or 0.0)

    return categories


def get_category(db: Session, category_id: int) -> Category | None:
    return db.get(Category, category_id)


def create_category(
    db: Session,
    *,
    user_id: int,
    name: str,
    type: str,
    icon: str | None = None,
    color: str | None = None,
    keywords: list[str] | None = None,
    budget_limit: float | None = None,
) -> Category:
    category = Category(
        user_id=user_id,
        name=name,
        type=type,
        icon=icon,
        color=color,
        keywords=keywords,
        budget_limit=budget_limit,
        is_default=False,
        is_active=True,
    )
    db.add(category)
    db.flush()
    category.spent_this_month = 0.0
    return category


def update_category(
    db: Session,
    category: Category,
    *,
    name: str | None = None,
    type: str | None = None,
    icon: str | None = ...,  # type: ignore[assignment]
    color: str | None = ...,  # type: ignore[assignment]
    keywords: list[str] | None = ...,  # type: ignore[assignment]
    budget_limit: float | None = ...,  # type: ignore[assignment]
    is_active: bool | None = None,
) -> Category:
    if name is not None:
        category.name = name
    if type is not None:
        category.type = type
    if icon is not ...:
        category.icon = icon  # type: ignore[assignment]
    if color is not ...:
        category.color = color  # type: ignore[assignment]
    if keywords is not ...:
        category.keywords = keywords  # type: ignore[assignment]
    if budget_limit is not ...:
        category.budget_limit = budget_limit  # type: ignore[assignment]
    if is_active is not None:
        category.is_active = is_active
    db.flush()
    # maintain attribute for response
    if not hasattr(category, "spent_this_month"):
        category.spent_this_month = 0.0
    return category


def soft_delete_category(db: Session, category: Category) -> None:
    category.is_active = False
    db.flush()


def category_exists(
    db: Session,
    *,
    user_id: int,
    name: str,
    type: str,
    exclude_id: int | None = None,
) -> bool:
    query = select(func.count(Category.id)).where(
        or_(Category.user_id == user_id, Category.user_id.is_(None)),
        func.lower(Category.name) == name.lower(),
        Category.type == type,
        Category.is_active == True,  # noqa: E712
    )
    if exclude_id is not None:
        query = query.where(Category.id != exclude_id)
    return (db.scalar(query) or 0) > 0
