from dataclasses import asdict, dataclass
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import BotLog


OCR_MESSAGE_TYPE = "receipt_ocr"
OCR_USAGE_STATUS = "ocr_usage"
OCR_LIMIT_REACHED_STATUS = "ocr_limit_reached"
DEFAULT_RATE_LIMIT_TIMEZONE = "Asia/Jakarta"


@dataclass(frozen=True)
class OcrRateLimitState:
    user_id: int
    limit: int
    used: int
    remaining: int
    window_start: datetime
    reset_at: datetime
    timezone: str

    def to_log_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["window_start"] = self.window_start.isoformat()
        payload["reset_at"] = self.reset_at.isoformat()
        return payload


class OcrRateLimitExceeded(Exception):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS

    def __init__(self, state: OcrRateLimitState) -> None:
        self.state = state
        self.detail = (
            f"Batas OCR harian tercapai ({state.limit} kali per hari). "
            f"Coba lagi setelah {state.reset_at.isoformat()}."
        )
        super().__init__(self.detail)


def enforce_ocr_daily_limit(
    db: Session,
    *,
    user_id: int,
    limit: int,
    timezone_name: str = DEFAULT_RATE_LIMIT_TIMEZONE,
    source: str,
    media_id: int | None = None,
) -> OcrRateLimitState:
    state = get_ocr_daily_limit_state(
        db,
        user_id=user_id,
        limit=limit,
        timezone_name=timezone_name,
    )
    if state.used >= state.limit:
        log_ocr_limit_reached(
            db,
            user_id=user_id,
            source=source,
            media_id=media_id,
            state=state,
        )
        db.commit()
        raise OcrRateLimitExceeded(state)
    return state


def get_ocr_daily_limit_state(
    db: Session,
    *,
    user_id: int,
    limit: int,
    timezone_name: str = DEFAULT_RATE_LIMIT_TIMEZONE,
) -> OcrRateLimitState:
    normalized_limit = max(limit, 0)
    timezone = _load_timezone(timezone_name)
    now = datetime.now(timezone)
    window_start = datetime.combine(now.date(), time.min, tzinfo=timezone)
    reset_at = window_start + timedelta(days=1)
    used = db.scalar(
        select(func.count(BotLog.id)).where(
            BotLog.user_id == user_id,
            BotLog.message_type == OCR_MESSAGE_TYPE,
            BotLog.status == OCR_USAGE_STATUS,
            BotLog.created_at >= window_start,
            BotLog.created_at < reset_at,
        )
    )
    used_count = int(used or 0)
    return OcrRateLimitState(
        user_id=user_id,
        limit=normalized_limit,
        used=used_count,
        remaining=max(normalized_limit - used_count, 0),
        window_start=window_start,
        reset_at=reset_at,
        timezone=timezone.key,
    )


def log_ocr_usage(
    db: Session,
    *,
    user_id: int,
    source: str,
    media_id: int,
    receipt_id: int | None,
    state: OcrRateLimitState,
    job_id: int | None = None,
    error_message: str | None = None,
) -> BotLog:
    payload = {
        "event": OCR_USAGE_STATUS,
        "job_id": job_id,
        "media_id": media_id,
        "receipt_id": receipt_id,
        "rate_limit": state.to_log_payload(),
        "used_after": state.used + 1,
        "remaining_after": max(state.remaining - 1, 0),
    }
    return _add_ocr_log(
        db,
        user_id=user_id,
        source=source,
        status=OCR_USAGE_STATUS,
        raw_message=f"media_id={media_id}",
        parsed_result=payload,
        error_message=error_message,
    )


def log_ocr_limit_reached(
    db: Session,
    *,
    user_id: int,
    source: str,
    media_id: int | None,
    state: OcrRateLimitState,
) -> BotLog:
    payload = {
        "event": OCR_LIMIT_REACHED_STATUS,
        "media_id": media_id,
        "rate_limit": state.to_log_payload(),
    }
    return _add_ocr_log(
        db,
        user_id=user_id,
        source=source,
        status=OCR_LIMIT_REACHED_STATUS,
        raw_message=f"media_id={media_id}" if media_id is not None else None,
        parsed_result=payload,
        error_message="OCR daily limit reached",
    )


def _add_ocr_log(
    db: Session,
    *,
    user_id: int,
    source: str,
    status: str,
    raw_message: str | None,
    parsed_result: dict[str, Any],
    error_message: str | None,
) -> BotLog:
    bot_log = BotLog(
        user_id=user_id,
        platform=_platform_from_source(source),
        message_type=OCR_MESSAGE_TYPE,
        raw_message=raw_message,
        parsed_result=parsed_result,
        status=status,
        error_message=error_message,
        created_at=datetime.now(_load_timezone(DEFAULT_RATE_LIMIT_TIMEZONE)),
    )
    db.add(bot_log)
    return bot_log


def _platform_from_source(source: str) -> str:
    normalized = source.strip().lower()
    if normalized.startswith("whatsapp"):
        return "whatsapp"
    if normalized.startswith("telegram"):
        return "telegram"
    if normalized.startswith("dashboard"):
        return "dashboard"
    return "system"


def _load_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name or DEFAULT_RATE_LIMIT_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_RATE_LIMIT_TIMEZONE)
