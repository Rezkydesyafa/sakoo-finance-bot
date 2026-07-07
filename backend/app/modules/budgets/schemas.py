from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class BudgetUpsertRequest(BaseModel):
    monthly_limit: Decimal = Field(..., gt=0, max_digits=14, decimal_places=2)


class BudgetItemResponse(BaseModel):
    category_id: int
    category_name: str
    monthly_limit: Decimal
    spent: Decimal
    remaining: Decimal
    usage_percentage: Decimal
    status: str


class BudgetListResponse(BaseModel):
    period_start: date
    period_end: date
    total_budgeted: Decimal
    total_spent: Decimal
    total_remaining: Decimal
    items: list[BudgetItemResponse]


class BudgetResponse(BudgetItemResponse):
    period_start: date
    period_end: date
