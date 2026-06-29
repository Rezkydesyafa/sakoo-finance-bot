from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import BotLog
from app.modules.llm.base import (
    BaseLlmProvider,
    LlmProviderConfig,
    LlmProviderError,
    expand_llm_response,
)
from app.modules.llm.deepseek_provider import DeepSeekProvider
from app.modules.llm.gemini_provider import GeminiProvider
from app.modules.llm.glm_provider import GlmProvider
from app.modules.llm.openrouter_provider import OpenRouterProvider


LLM_MESSAGE_TYPE = "llm_fallback"
LLM_USAGE_STATUS = "llm_usage"
LLM_LIMIT_REACHED_STATUS = "llm_limit_reached"
DEFAULT_RATE_LIMIT_TIMEZONE = "Asia/Jakarta"


class LlmProviderUnavailable(LlmProviderError):
    pass


class LlmRateLimitExceeded(LlmProviderError):
    pass


@dataclass(frozen=True)
class LlmRateLimitState:
    user_id: int
    limit: int
    used: int
    remaining: int
    window_start: datetime
    reset_at: datetime
    timezone: str

    def to_log_payload(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "limit": self.limit,
            "used": self.used,
            "remaining": self.remaining,
            "window_start": self.window_start.isoformat(),
            "reset_at": self.reset_at.isoformat(),
            "timezone": self.timezone,
        }


def parse_transaction_with_llm(
    message: str,
    *,
    source: str = "llm_fallback",
    user_id: int | None = None,
    db: Session | None = None,
    today: Any = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    active_settings = settings or get_settings()
    provider = get_llm_provider(active_settings)
    if provider is None:
        raise LlmProviderUnavailable("llm_provider_disabled")

    state = None
    if db is not None and user_id is not None:
        state = enforce_llm_daily_limit(
            db,
            user_id=user_id,
            limit=active_settings.llm_max_request_per_user_per_day,
        )

    compact_result = provider.parse_transaction(message)
    expanded = expand_llm_response(compact_result, source=source, today=today)

    if db is not None and user_id is not None and state is not None:
        log_llm_usage(
            db,
            user_id=user_id,
            provider=provider.provider_name,
            result=expanded,
            state=state,
        )

    return expanded


def get_llm_provider(settings: Settings | None = None) -> BaseLlmProvider | None:
    active_settings = settings or get_settings()
    provider_name = active_settings.llm_provider.strip().lower()
    timeout = active_settings.llm_timeout_seconds

    if provider_name in {"", "none", "off", "disabled"}:
        return None
    if provider_name == "gemini":
        return GeminiProvider(
            LlmProviderConfig(
                api_key=active_settings.gemini_api_key,
                timeout_seconds=timeout,
            )
        )
    if provider_name == "glm":
        return GlmProvider(
            LlmProviderConfig(
                api_key=active_settings.glm_api_key,
                timeout_seconds=timeout,
            )
        )
    if provider_name == "openrouter":
        return OpenRouterProvider(
            LlmProviderConfig(
                api_key=active_settings.openrouter_api_key,
                timeout_seconds=timeout,
            )
        )
    if provider_name == "deepseek":
        return DeepSeekProvider(
            LlmProviderConfig(
                api_key=active_settings.deepseek_api_key,
                timeout_seconds=timeout,
            )
        )
    raise LlmProviderUnavailable("llm_provider_unknown")


def enforce_llm_daily_limit(
    db: Session,
    *,
    user_id: int,
    limit: int,
    timezone_name: str = DEFAULT_RATE_LIMIT_TIMEZONE,
) -> LlmRateLimitState:
    state = get_llm_daily_limit_state(
        db,
        user_id=user_id,
        limit=limit,
        timezone_name=timezone_name,
    )
    if state.used >= state.limit:
        log_llm_limit_reached(db, user_id=user_id, state=state)
        raise LlmRateLimitExceeded("llm_daily_limit_reached")
    return state


def get_llm_daily_limit_state(
    db: Session,
    *,
    user_id: int,
    limit: int,
    timezone_name: str = DEFAULT_RATE_LIMIT_TIMEZONE,
) -> LlmRateLimitState:
    normalized_limit = max(limit, 0)
    timezone = _load_timezone(timezone_name)
    now = datetime.now(timezone)
    window_start = datetime.combine(now.date(), time.min, tzinfo=timezone)
    reset_at = window_start + timedelta(days=1)
    used = db.scalar(
        select(func.count(BotLog.id)).where(
            BotLog.user_id == user_id,
            BotLog.message_type == LLM_MESSAGE_TYPE,
            BotLog.status == LLM_USAGE_STATUS,
            BotLog.created_at >= window_start,
            BotLog.created_at < reset_at,
        )
    )
    used_count = int(used or 0)
    return LlmRateLimitState(
        user_id=user_id,
        limit=normalized_limit,
        used=used_count,
        remaining=max(normalized_limit - used_count, 0),
        window_start=window_start,
        reset_at=reset_at,
        timezone=timezone.key,
    )


def log_llm_usage(
    db: Session,
    *,
    user_id: int,
    provider: str,
    result: dict[str, Any],
    state: LlmRateLimitState,
) -> BotLog:
    payload = {
        "event": LLM_USAGE_STATUS,
        "provider": provider,
        "intent": result.get("intent"),
        "type": result.get("type"),
        "amount_present": result.get("amount") is not None,
        "category": result.get("category"),
        "confidence": result.get("confidence"),
        "need_confirmation": result.get("need_confirmation"),
        "rate_limit": state.to_log_payload(),
        "used_after": state.used + 1,
        "remaining_after": max(state.remaining - 1, 0),
    }
    bot_log = BotLog(
        user_id=user_id,
        platform="system",
        message_type=LLM_MESSAGE_TYPE,
        raw_message=None,
        parsed_result=payload,
        status=LLM_USAGE_STATUS,
    )
    db.add(bot_log)
    return bot_log


def log_llm_limit_reached(
    db: Session,
    *,
    user_id: int,
    state: LlmRateLimitState,
) -> BotLog:
    bot_log = BotLog(
        user_id=user_id,
        platform="system",
        message_type=LLM_MESSAGE_TYPE,
        raw_message=None,
        parsed_result={
            "event": LLM_LIMIT_REACHED_STATUS,
            "rate_limit": state.to_log_payload(),
        },
        status=LLM_LIMIT_REACHED_STATUS,
        error_message="LLM daily limit reached",
    )
    db.add(bot_log)
    return bot_log


def _load_timezone(timezone_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(timezone_name or DEFAULT_RATE_LIMIT_TIMEZONE)
    except ZoneInfoNotFoundError:
        return ZoneInfo(DEFAULT_RATE_LIMIT_TIMEZONE)
