from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.modules.auth.dependencies import get_current_user
from app.modules.notifications.schemas import (
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
)
from app.modules.notifications.service import get_preferences, update_preferences

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/preferences", response_model=NotificationPreferencesResponse)
def read_notification_preferences(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> NotificationPreferencesResponse:
    return get_preferences(db, current_user.id)


@router.put("/preferences", response_model=NotificationPreferencesResponse)
def save_notification_preferences(
    payload: NotificationPreferencesUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> NotificationPreferencesResponse:
    return update_preferences(db, current_user.id, payload)
