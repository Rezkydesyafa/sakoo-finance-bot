from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransactionCreateRequest(BaseModel):
    type: str = Field(pattern="^(income|expense)$")
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    category_id: int | None = None
    description: str | None = Field(default=None, max_length=500)
    transaction_date: date = Field(default_factory=date.today)

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else None
        return normalized or None


class TransactionUpdateRequest(BaseModel):
    type: str | None = Field(default=None, pattern="^(income|expense)$")
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    category_id: int | None = None
    description: str | None = Field(default=None, max_length=500)
    transaction_date: date | None = None

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        normalized = value.strip() if value else None
        return normalized or None


class TransactionTextParseRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()


class TransactionTextParseResponse(BaseModel):
    status: str
    reply_text: str
    transaction_id: int | None = None


class TransactionResponse(BaseModel):
    id: int
    type: str
    amount: Decimal
    category_id: int | None
    category_name: str | None
    description: str | None
    transaction_date: date
    source: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
    limit: int
    offset: int
    has_next: bool
