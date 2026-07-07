from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.modules.auth.dependencies import get_current_user
from app.modules.budgets.schemas import (
    BudgetItemResponse,
    BudgetListResponse,
    BudgetResponse,
    BudgetUpsertRequest,
)
from app.modules.budgets.service import (
    build_budget_item,
    delete_category_budget,
    get_budget_overview,
    get_visible_expense_category,
    month_bounds,
    upsert_category_budget,
)

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("", response_model=BudgetListResponse)
def list_budgets(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BudgetListResponse:
    overview = get_budget_overview(db, current_user.id)
    return BudgetListResponse(
        period_start=overview.period_start,
        period_end=overview.period_end,
        total_budgeted=overview.total_budgeted,
        total_spent=overview.total_spent,
        total_remaining=overview.total_remaining,
        items=[BudgetItemResponse(**item.__dict__) for item in overview.items],
    )


@router.put("/{category_id}", response_model=BudgetResponse)
def set_budget(
    category_id: int,
    payload: BudgetUpsertRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BudgetResponse:
    category = get_visible_expense_category(db, user_id=current_user.id, category_id=category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense category not found",
        )

    budget = upsert_category_budget(
        db,
        user_id=current_user.id,
        category=category,
        monthly_limit=payload.monthly_limit,
    )
    db.commit()
    db.refresh(budget)
    period_start, period_end = month_bounds(date.today())
    item = build_budget_item(db, budget, period_start=period_start, period_end=period_end)
    return BudgetResponse(period_start=period_start, period_end=period_end, **item.__dict__)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_budget(
    category_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    category = get_visible_expense_category(db, user_id=current_user.id, category_id=category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Expense category not found",
        )

    delete_category_budget(db, user_id=current_user.id, category_id=category_id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
