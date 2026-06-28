import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import BotLog
from app.modules.waha.client import WahaClient, WahaClientError, get_waha_client


logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])
WAHA_HEALTHY_STATUS = "WORKING"


class WahaHealthResponse(BaseModel):
    status: str
    healthy: bool
    session: str
    session_status: str | None
    warning: str | None = None
    checked_at: str
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class WahaHealthResult:
    status: str
    healthy: bool
    session: str
    session_status: str | None
    warning: str | None
    checked_at: str
    raw: dict[str, Any] | None = None

    def to_response(self) -> WahaHealthResponse:
        return WahaHealthResponse(**asdict(self))


@router.get("/health/waha", response_model=WahaHealthResponse)
def waha_health_check(
    db: Session = Depends(get_db),
    waha_client: WahaClient = Depends(get_waha_client),
) -> WahaHealthResponse:
    result = check_waha_health(waha_client)
    if not result.healthy:
        _record_waha_health_warning(db=db, result=result)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=result.to_response().model_dump(),
        )

    return result.to_response()


def check_waha_health(waha_client: WahaClient) -> WahaHealthResult:
    session = getattr(waha_client, "session", None) or get_settings().waha_session_name
    checked_at = datetime.now(timezone.utc).isoformat()
    try:
        payload = waha_client.get_session_status(session=session)
    except WahaClientError as exc:
        warning = f"WAHA health check failed: {exc}"
        logger.warning(warning, exc_info=True)
        return WahaHealthResult(
            status="error",
            healthy=False,
            session=session,
            session_status=None,
            warning=warning,
            checked_at=checked_at,
            raw={
                "status_code": exc.status_code,
                "response_body": exc.response_body,
            },
        )

    session_status = _extract_session_status(payload)
    if session_status != WAHA_HEALTHY_STATUS:
        warning = (
            "WAHA session is not active. "
            f"session={session}, status={session_status or 'unknown'}"
        )
        logger.warning(warning)
        return WahaHealthResult(
            status="error",
            healthy=False,
            session=session,
            session_status=session_status,
            warning=warning,
            checked_at=checked_at,
            raw=payload,
        )

    return WahaHealthResult(
        status="ok",
        healthy=True,
        session=session,
        session_status=session_status,
        warning=None,
        checked_at=checked_at,
        raw=payload,
    )


def _extract_session_status(payload: dict[str, Any]) -> str | None:
    raw_status = payload.get("status")
    if not raw_status and isinstance(payload.get("data"), dict):
        raw_status = payload["data"].get("status")
    if not raw_status:
        return None
    return str(raw_status).upper()


def _record_waha_health_warning(*, db: Session, result: WahaHealthResult) -> None:
    bot_log = BotLog(
        user_id=None,
        platform="system",
        message_type="waha_health",
        raw_message=result.warning,
        parsed_result=result.to_response().model_dump(),
        status="waha_unhealthy",
        error_message=result.warning,
    )
    try:
        db.add(bot_log)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to persist WAHA health warning to bot_logs.")
