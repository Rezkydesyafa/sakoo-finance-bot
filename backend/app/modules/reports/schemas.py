from datetime import date
from decimal import Decimal

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.media.schemas import MediaFileResponse


class ReportTransactionItem(BaseModel):
    id: int
    type: str
    amount: Decimal
    category_id: int | None
    category_name: str | None
    description: str | None
    transaction_date: date
    source: str

    model_config = ConfigDict(from_attributes=True)


class ReportSummaryResponse(BaseModel):
    report_type: str
    period_start: date
    period_end: date
    total_income: Decimal
    total_expense: Decimal
    net_balance: Decimal
    transaction_count: int
    income_count: int
    expense_count: int
    transactions: list[ReportTransactionItem]
    total_transactions: int
    limit: int
    offset: int
    has_next: bool


class ReportCategoryItem(BaseModel):
    category_id: int | None
    category_name: str
    type: str
    total_amount: Decimal
    transaction_count: int
    percentage: Decimal


class ReportCategoryResponse(BaseModel):
    report_type: str
    period_start: date
    period_end: date
    type: str | None
    total_amount: Decimal
    items: list[ReportCategoryItem]


class ReportPdfGenerateRequest(BaseModel):
    period: str = Field(default="month", pattern="^(day|week|month|custom)$")
    anchor_date: date | None = Field(default=None, alias="date")
    start_date: date | None = None
    end_date: date | None = None
    generated_from: str = Field(default="dashboard", pattern="^[a-z0-9_:-]{1,40}$")

    model_config = ConfigDict(populate_by_name=True)


class ReportResponse(BaseModel):
    id: int
    user_id: int
    period_start: date
    period_end: date
    report_type: str
    file_id: int | None
    generated_from: str
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReportPdfGenerateResponse(BaseModel):
    report: ReportResponse
    file: MediaFileResponse
    download_url: str
