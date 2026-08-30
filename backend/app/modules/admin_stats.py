from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Annotated, Any
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.database import get_db
from app.models import BotLog, Transaction, User
from app.modules.auth.admin import is_admin_email
from app.modules.auth.dependencies import get_current_user

router = APIRouter(prefix="/admin", tags=["admin-stats"])


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not is_admin_email(user.email):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


class AdminOverviewStatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_transactions: int
    total_llm_requests: int


class AdminUserItem(BaseModel):
    id: int
    name: str
    email: str
    phone_number: str | None
    created_at: datetime
    transaction_count: int
    last_active: datetime | None


class AdminUserListResponse(BaseModel):
    items: list[AdminUserItem]
    total: int


class LlmLogItem(BaseModel):
    id: int
    user_id: int | None
    user_name: str | None
    user_email: str | None
    platform: str
    message_type: str
    provider: str | None
    intent: str | None
    status: str
    raw_message: str | None
    parsed_result: dict[str, Any] | None
    error_message: str | None
    created_at: datetime


class LlmLogListResponse(BaseModel):
    items: list[LlmLogItem]
    total: int


@router.get("/stats", response_model=AdminOverviewStatsResponse)
def get_admin_stats(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> AdminOverviewStatsResponse:
    total_users = db.scalar(select(func.count(User.id))) or 0
    
    # Active users: users with transactions or bot logs in the last 30 days
    active_users = db.scalar(
        select(func.count(func.distinct(User.id)))
        .select_from(User)
        .outerjoin(Transaction, Transaction.user_id == User.id)
        .where(Transaction.id.is_not(None))
    ) or 0

    total_transactions = db.scalar(select(func.count(Transaction.id))) or 0
    
    total_llm_requests = db.scalar(
        select(func.count(BotLog.id))
        .where(BotLog.message_type == "llm_chat")
    ) or 0

    return AdminOverviewStatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_transactions=total_transactions,
        total_llm_requests=total_llm_requests,
    )


@router.get("/users", response_model=AdminUserListResponse)
def list_admin_users(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> AdminUserListResponse:
    users = list(
        db.scalars(
            select(User)
            .order_by(User.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    total = db.scalar(select(func.count(User.id))) or 0

    items: list[AdminUserItem] = []
    for u in users:
        tx_count = db.scalar(
            select(func.count(Transaction.id)).where(Transaction.user_id == u.id)
        ) or 0
        last_tx = db.scalar(
            select(func.max(Transaction.created_at)).where(Transaction.user_id == u.id)
        )
        items.append(
            AdminUserItem(
                id=u.id,
                name=u.name,
                email=u.email,
                phone_number=u.phone_number,
                created_at=u.created_at,
                transaction_count=tx_count,
                last_active=last_tx,
            )
        )

    return AdminUserListResponse(items=items, total=total)


@router.get("/llm-logs", response_model=LlmLogListResponse)
def list_llm_logs(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[Session, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> LlmLogListResponse:
    logs = list(
        db.scalars(
            select(BotLog)
            .where(BotLog.message_type == "llm_chat")
            .order_by(BotLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    total = db.scalar(
        select(func.count(BotLog.id)).where(BotLog.message_type == "llm_chat")
    ) or 0

    items: list[LlmLogItem] = []
    for log in logs:
        u_name = log.user.name if log.user else None
        u_email = log.user.email if log.user else None
        provider = None
        intent = None
        if isinstance(log.parsed_result, dict):
            provider = log.parsed_result.get("provider")
            intent = log.parsed_result.get("intent")

        items.append(
            LlmLogItem(
                id=log.id,
                user_id=log.user_id,
                user_name=u_name,
                user_email=u_email,
                platform=log.platform,
                message_type=log.message_type,
                provider=provider,
                intent=intent,
                status=log.status,
                raw_message=log.raw_message,
                parsed_result=log.parsed_result,
                error_message=log.error_message,
                created_at=log.created_at,
            )
        )

    return LlmLogListResponse(items=items, total=total)
