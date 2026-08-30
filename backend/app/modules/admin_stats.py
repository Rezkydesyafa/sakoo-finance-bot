from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import BotLog, Transaction, User
from app.modules.auth.admin import is_admin_email
from app.modules.auth.dependencies import get_current_user

router = APIRouter(prefix="/admin", tags=["admin-stats"])


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if not is_admin_email(user.email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can access this resource",
        )
    return user


class AdminStatsResponse(BaseModel):
    total_users: int
    active_users: int
    total_transactions: int
    total_llm_requests: int


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
    created_at: datetime


class LlmLogsResponse(BaseModel):
    items: list[LlmLogItem]
    total: int


class AdminUserItem(BaseModel):
    id: int
    name: str
    email: str
    phone_number: str | None
    created_at: datetime
    transaction_count: int
    last_active: datetime | None


class AdminUsersResponse(BaseModel):
    items: list[AdminUserItem]
    total: int


@router.get("/stats", response_model=AdminStatsResponse)
def get_admin_stats(
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[User, Depends(require_admin)],
):
    # Total Users
    total_users = db.scalar(select(func.count()).select_from(User)) or 0

    # Total Transactions
    total_transactions = db.scalar(select(func.count()).select_from(Transaction)) or 0

    # Total LLM Requests (BotLog status = 'llm_usage' or messaging logic)
    total_llm_requests = db.scalar(
        select(func.count())
        .select_from(BotLog)
        .where(
            BotLog.status.in_(["success", "transaction_finance_chat", "llm_usage"])
        )
    ) or 0

    # Active Users in last 30 days (users who made a transaction or had bot logs)
    # We query distinct user_id from Transaction in the last 30 days
    # (Actually we can just count users who have any activity, or general active users)
    thirty_days_ago = datetime.utcnow()
    # Simple active user calculation
    active_users = db.scalar(
        select(func.count(User.id.distinct()))
        .select_from(User)
        .join(Transaction, Transaction.user_id == User.id, isouter=True)
        .where(Transaction.created_at >= thirty_days_ago)
    ) or 0

    return {
        "total_users": total_users,
        "active_users": active_users,
        "total_transactions": total_transactions,
        "total_llm_requests": total_llm_requests,
    }


@router.get("/llm-logs", response_model=LlmLogsResponse)
def get_llm_logs(
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[User, Depends(require_admin)],
    limit: int = 50,
    offset: int = 0,
):
    # Fetch bot logs and join User if possible
    query = (
        select(BotLog, User.name, User.email)
        .join(User, BotLog.user_id == User.id, isouter=True)
        .order_by(BotLog.created_at.desc())
    )

    total = db.scalar(select(func.count()).select_from(BotLog)) or 0
    results = db.execute(query.limit(limit).offset(offset)).all()

    items = []
    for bot_log, u_name, u_email in results:
        items.append(
            {
                "id": bot_log.id,
                "user_id": bot_log.user_id,
                "user_name": u_name,
                "user_email": u_email,
                "platform": bot_log.platform,
                "message_type": bot_log.message_type,
                "provider": bot_log.provider,
                "intent": bot_log.intent,
                "status": bot_log.status,
                "raw_message": bot_log.raw_message,
                "created_at": bot_log.created_at,
            }
        )

    return {"items": items, "total": total}


@router.get("/users", response_model=AdminUsersResponse)
def get_admin_users(
    db: Annotated[Session, Depends(get_db)],
    current_admin: Annotated[User, Depends(require_admin)],
    limit: int = 50,
    offset: int = 0,
):
    # Query users and count their transactions
    query = (
        select(
            User,
            func.count(Transaction.id).label("txn_count"),
            func.max(Transaction.created_at).label("last_active"),
        )
        .join(Transaction, Transaction.user_id == User.id, isouter=True)
        .group_by(User.id)
        .order_by(User.created_at.desc())
    )

    total = db.scalar(select(func.count()).select_from(User)) or 0
    results = db.execute(query.limit(limit).offset(offset)).all()

    items = []
    for user, txn_count, last_active in results:
        items.append(
            {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "phone_number": user.phone_number,
                "created_at": user.created_at,
                "transaction_count": txn_count or 0,
                "last_active": last_active,
            }
        )

    return {"items": items, "total": total}
