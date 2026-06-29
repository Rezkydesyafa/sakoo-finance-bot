from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.modules.llm.base import LlmProviderError
from app.modules.llm.llm_router import parse_transaction_with_llm
from app.modules.parser.schemas import (
    INTENT_ADD_TRANSACTION,
    INTENT_UNKNOWN,
    LLM_FALLBACK_THRESHOLD,
)
from app.modules.parser.service import ParsedMessage, parse_message


def parse_bot_text_message(
    *,
    db: Session,
    user_id: int,
    text: str,
    source: str,
    today: date | None = None,
) -> tuple[ParsedMessage, str | None]:
    local_result = parse_message(text, source=source, today=today)
    if not should_use_llm_fallback(local_result):
        return local_result, None

    try:
        llm_result = parse_transaction_with_llm(
            text,
            source=source,
            user_id=user_id,
            db=db,
            today=today,
        )
    except LlmProviderError as exc:
        return local_result, exc.detail

    return _parsed_message_from_llm_result(llm_result), None


def should_use_llm_fallback(parse_result: ParsedMessage) -> bool:
    if parse_result.intent == INTENT_UNKNOWN:
        return True
    if parse_result.intent != INTENT_ADD_TRANSACTION:
        return False
    if parse_result.amount is None:
        return False
    return parse_result.confidence < LLM_FALLBACK_THRESHOLD


def _parsed_message_from_llm_result(payload: dict[str, Any]) -> ParsedMessage:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    return ParsedMessage(
        intent=str(payload["intent"]),
        type=payload.get("type"),
        amount=_decimal_or_none(payload.get("amount")),
        category=payload.get("category"),
        description=payload.get("description"),
        transaction_date=payload.get("transaction_date"),
        source=str(payload["source"]),
        confidence=float(payload["confidence"]),
        need_confirmation=bool(payload["need_confirmation"]),
        reasons=list(payload.get("reasons") or ["llm_fallback"]),
        period=payload.get("period"),
        category_confidence=float(payload["confidence"]),
        category_source=f"llm:{metadata.get('llm_category_code', 'unknown')}",
    )


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))
