from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class CategoryResponse(BaseModel):
    id: int
    user_id: int | None = None
    name: str
    type: str
    icon: str | None = None
    color: str | None = None
    keywords: list[str] | None = None
    is_default: bool = False
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CategoryCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    type: str = Field(..., pattern=r"^(income|expense|both)$")
    icon: str | None = Field(None, max_length=32)
    color: str | None = Field(None, max_length=32)
    keywords: list[str] | None = None


class CategoryUpdateRequest(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=80)
    type: str | None = Field(None, pattern=r"^(income|expense|both)$")
    icon: str | None = Field(None, max_length=32)
    color: str | None = Field(None, max_length=32)
    keywords: list[str] | None = None
    is_active: bool | None = None


class CategoryKeywordsRequest(BaseModel):
    keywords: list[str] = Field(..., max_length=50)


class CategoryListResponse(BaseModel):
    items: list[CategoryResponse]
    total: int
