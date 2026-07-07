from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, CategoryBudget, Transaction

CONFIRMED_TRANSACTION_STATUS = "confirmed"


@dataclass(frozen=True)
class BudgetItem:
    category_id: int
    category_name: str
    monthly_limit: Decimal
    spent: Decimal
    remaining: Decimal
    usage_percentage: Decimal
    status: str


@dataclass(frozen=True)
class BudgetOverview:
    period_start: date
    period_end: date
    total_budgeted: Decimal
    total_spent: Decimal
    total_remaining: Decimal
    items: list[BudgetItem]


def get_budget_overview(
    db: Session,
    user_id: int,
    *,
    today: date | None = None,
) -> BudgetOverview:
    period_start, period_end = month_bounds(today or date.today())
    budgets = list(
        db.scalars(
            select(CategoryBudget)
            .join(Category, CategoryBudget.category_id == Category.id)
            .where(
                CategoryBudget.user_id == user_id,
                Category.is_active.is_(True),
                Category.type.in_(("expense", "both")),
                ((Category.user_id == user_id) | Category.user_id.is_(None)),
            )
            .order_by(Category.name.asc(), CategoryBudget.id.asc())
        )
    )
    items = [
        build_budget_item(db, budget, period_start=period_start, period_end=period_end)
        for budget in budgets
    ]
    total_budgeted = sum((item.monthly_limit for item in items), Decimal("0"))
    total_spent = sum((item.spent for item in items), Decimal("0"))
    return BudgetOverview(
        period_start=period_start,
        period_end=period_end,
        total_budgeted=total_budgeted,
        total_spent=total_spent,
        total_remaining=total_budgeted - total_spent,
        items=items,
    )


def get_budget_for_category(
    db: Session,
    user_id: int,
    category: Category,
    *,
    today: date | None = None,
) -> tuple[date, date, BudgetItem] | None:
    budget = db.scalar(
        select(CategoryBudget).where(
            CategoryBudget.user_id == user_id,
            CategoryBudget.category_id == category.id,
        )
    )
    if budget is None:
        return None
    period_start, period_end = month_bounds(today or date.today())
    return period_start, period_end, build_budget_item(
        db,
        budget,
        period_start=period_start,
        period_end=period_end,
    )


def upsert_category_budget(
    db: Session,
    *,
    user_id: int,
    category: Category,
    monthly_limit: Decimal,
) -> CategoryBudget:
    budget = db.scalar(
        select(CategoryBudget).where(
            CategoryBudget.user_id == user_id,
            CategoryBudget.category_id == category.id,
        )
    )
    if budget is None:
        budget = CategoryBudget(
            user_id=user_id,
            category_id=category.id,
            monthly_limit=monthly_limit,
        )
        db.add(budget)
    else:
        budget.monthly_limit = monthly_limit
    db.flush()
    return budget


def delete_category_budget(db: Session, *, user_id: int, category_id: int) -> bool:
    budget = db.scalar(
        select(CategoryBudget).where(
            CategoryBudget.user_id == user_id,
            CategoryBudget.category_id == category_id,
        )
    )
    if budget is None:
        return False
    db.delete(budget)
    db.flush()
    return True


def get_visible_expense_category(
    db: Session,
    *,
    user_id: int,
    category_id: int,
) -> Category | None:
    return db.scalar(
        select(Category).where(
            Category.id == category_id,
            Category.is_active.is_(True),
            Category.type.in_(("expense", "both")),
            ((Category.user_id == user_id) | Category.user_id.is_(None)),
        )
    )


def find_visible_expense_category_by_name(
    db: Session,
    *,
    user_id: int,
    name: str,
) -> Category | None:
    return db.scalar(
        select(Category)
        .where(
            func.lower(Category.name) == name.lower(),
            Category.is_active.is_(True),
            Category.type.in_(("expense", "both")),
            ((Category.user_id == user_id) | Category.user_id.is_(None)),
        )
        .order_by(Category.user_id.is_(None).asc())
    )


def build_budget_item(
    db: Session,
    budget: CategoryBudget,
    *,
    period_start: date,
    period_end: date,
) -> BudgetItem:
    spent = budget_spent(
        db,
        user_id=budget.user_id,
        category_id=budget.category_id,
        period_start=period_start,
        period_end=period_end,
    )
    remaining = budget.monthly_limit - spent
    usage_percentage = (
        (spent / budget.monthly_limit * Decimal("100")).quantize(Decimal("0.01"))
        if budget.monthly_limit > 0
        else Decimal("0.00")
    )
    return BudgetItem(
        category_id=budget.category_id,
        category_name=budget.category.name if budget.category else "Tanpa kategori",
        monthly_limit=budget.monthly_limit,
        spent=spent,
        remaining=remaining,
        usage_percentage=usage_percentage,
        status=budget_status(usage_percentage),
    )


def budget_spent(
    db: Session,
    *,
    user_id: int,
    category_id: int,
    period_start: date,
    period_end: date,
) -> Decimal:
    value = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            Transaction.user_id == user_id,
            Transaction.category_id == category_id,
            Transaction.type == "expense",
            Transaction.status == CONFIRMED_TRANSACTION_STATUS,
            Transaction.transaction_date >= period_start,
            Transaction.transaction_date <= period_end,
        )
    )
    return Decimal(str(value or 0))


def budget_status(usage_percentage: Decimal) -> str:
    if usage_percentage >= Decimal("100"):
        return "over_budget"
    if usage_percentage >= Decimal("70"):
        return "warning"
    return "healthy"


def month_bounds(value: date) -> tuple[date, date]:
    start = value.replace(day=1)
    next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start, next_month - timedelta(days=1)
