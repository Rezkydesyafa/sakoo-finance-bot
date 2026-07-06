from __future__ import annotations

import re
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
)
from app.modules.llm.deepseek_provider import DeepSeekProvider
from app.modules.llm.gemini_provider import GeminiProvider
from app.modules.llm.glm_provider import GlmProvider
from app.modules.llm.ollama_provider import OllamaProvider
from app.modules.llm.openrouter_provider import OpenRouterProvider


LLM_MESSAGE_TYPE = "llm_chat"
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


def answer_finance_question_with_llm(
    message: str,
    *,
    context: str,
    user_id: int | None = None,
    db: Session | None = None,
    settings: Settings | None = None,
) -> str:
    active_settings = settings or get_settings()
    providers = get_llm_providers(active_settings)
    if not providers:
        raise LlmProviderUnavailable("llm_provider_disabled")

    state = None
    if db is not None and user_id is not None:
        state = enforce_llm_daily_limit(
            db,
            user_id=user_id,
            limit=active_settings.llm_max_request_per_user_per_day,
        )

    errors: list[str] = []
    for provider in providers:
        try:
            answer = provider.answer_finance_question(message, context=context)
        except LlmProviderError as exc:
            errors.append(f"{provider.provider_name}:{exc.detail}")
            continue

        cleaned = _clean_answer(answer)
        if not cleaned:
            errors.append(f"{provider.provider_name}:empty_answer")
            continue

        if db is not None and user_id is not None and state is not None:
            log_llm_usage(
                db,
                user_id=user_id,
                provider=provider.provider_name,
                result={
                    "intent": "finance_chat",
                    "type": None,
                    "amount": None,
                    "category": None,
                    "confidence": 1,
                    "need_confirmation": False,
                },
                state=state,
            )

        return cleaned

    detail = ";".join(errors) if errors else "no_provider_attempted"
    raise LlmProviderError(f"llm_all_providers_failed:{detail}")


def get_llm_provider(settings: Settings | None = None) -> BaseLlmProvider | None:
    providers = get_llm_providers(settings)
    return providers[0] if providers else None


def get_llm_providers(settings: Settings | None = None) -> list[BaseLlmProvider]:
    active_settings = settings or get_settings()
    provider_names = _resolve_provider_names(active_settings)
    timeout = active_settings.llm_timeout_seconds

    providers: list[BaseLlmProvider] = []
    for provider_name in provider_names:
        if provider_name in {"", "none", "off", "disabled"}:
            continue
        if provider_name == "gemini":
            gemini_keys = _gemini_api_keys(active_settings)
            if not gemini_keys:
                providers.append(
                    GeminiProvider(
                        LlmProviderConfig(
                            api_key="",
                            timeout_seconds=timeout,
                            model=active_settings.gemini_model,
                        )
                    )
                )
                continue
            providers.extend(
                GeminiProvider(
                    LlmProviderConfig(
                        api_key=api_key,
                        timeout_seconds=timeout,
                        model=active_settings.gemini_model,
                    )
                )
                for api_key in gemini_keys
            )
            continue
        if provider_name == "glm":
            providers.append(
                GlmProvider(
                    LlmProviderConfig(
                        api_key=active_settings.glm_api_key,
                        timeout_seconds=timeout,
                        model=active_settings.glm_model,
                    )
                )
            )
            continue
        if provider_name == "openrouter":
            providers.append(
                OpenRouterProvider(
                    LlmProviderConfig(
                        api_key=active_settings.openrouter_api_key,
                        timeout_seconds=timeout,
                        model=active_settings.openrouter_model,
                    )
                )
            )
            continue
        if provider_name == "deepseek":
            providers.append(
                DeepSeekProvider(
                    LlmProviderConfig(
                        api_key=active_settings.deepseek_api_key,
                        timeout_seconds=timeout,
                        model=active_settings.deepseek_model,
                    )
                )
            )
            continue
        if provider_name == "ollama":
            providers.append(
                OllamaProvider(
                    LlmProviderConfig(
                        api_key="",
                        timeout_seconds=active_settings.ollama_timeout_seconds,
                        model=active_settings.ollama_model,
                    ),
                    base_url=active_settings.ollama_base_url,
                )
            )
            continue
        raise LlmProviderUnavailable(f"llm_provider_unknown:{provider_name}")

    return providers


def _resolve_provider_names(settings: Settings) -> list[str]:
    provider_names = _parse_provider_names(settings.llm_provider)
    if provider_names and provider_names != ["none"]:
        return provider_names

    inferred: list[str] = []
    if _gemini_api_keys(settings):
        inferred.append("gemini")
    if settings.openrouter_api_key.strip():
        inferred.append("openrouter")
    return inferred or provider_names


def _parse_provider_names(value: str) -> list[str]:
    return [
        item
        for item in re.split(r"[\s,;|+>]+", value.strip().lower())
        if item
    ]


def _clean_answer(value: str) -> str:
    text = re.sub(r"\s+\n", "\n", str(value or "")).strip()
    return text[:1800]


def _gemini_api_keys(settings: Settings) -> list[str]:
    raw_values = [
        settings.gemini_api_key,
        settings.gemini_api_key_1,
        settings.gemini_api_key_2,
        *re.split(r"[\s,;|]+", settings.gemini_api_keys),
    ]
    keys: list[str] = []
    for value in raw_values:
        normalized = value.strip()
        if normalized and normalized not in keys:
            keys.append(normalized)
    return keys


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
