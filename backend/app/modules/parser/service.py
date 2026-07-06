from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from app.modules.parser.category_classifier import CategoryPrediction, predict_category
from app.modules.parser.transaction_text import (
    INTENT_ADD_TRANSACTION,
    ParsedTransactionText,
    parse_transaction_text,
)


AUTO_SAVE_CONFIDENCE = 0.85
CATEGORY_MODEL_MIN_CONFIDENCE = 0.25


@dataclass(frozen=True)
class ParsedMessage:
    intent: str
    type: str | None
    amount: Decimal | None
    category: str | None
    description: str | None
    transaction_date: date | None
    source: str
    confidence: float
    need_confirmation: bool
    reasons: list[str]
    period: str | None = None
    category_confidence: float | None = None
    category_source: str | None = None
    limit: int | None = None
    sort_order: str | None = None
    category_filter: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "intent": self.intent,
            "type": self.type,
            "amount": int(self.amount) if self.amount is not None else None,
            "category": self.category,
            "description": self.description,
            "transaction_date": self.transaction_date.isoformat()
            if self.transaction_date
            else None,
            "source": self.source,
            "confidence": round(self.confidence, 4),
            "need_confirmation": self.need_confirmation,
        }
        if self.reasons:
            payload["reasons"] = self.reasons
        if self.period:
            payload["period"] = self.period
        if self.limit is not None:
            payload["limit"] = self.limit
        if self.sort_order:
            payload["sort_order"] = self.sort_order
        if self.category_filter:
            payload["category_filter"] = self.category_filter
        if self.category_confidence is not None or self.category_source:
            payload["metadata"] = {
                "category_confidence": round(self.category_confidence or 0.0, 4),
                "category_source": self.category_source,
            }
        return payload

    def to_log_payload(self) -> dict[str, Any]:
        return self.to_dict()


def parse_message(
    text: str,
    source: str,
    *,
    today: date | None = None,
) -> ParsedMessage:
    base_result = parse_transaction_text(text, today=today)
    if base_result.intent != INTENT_ADD_TRANSACTION:
        return ParsedMessage(
            intent=base_result.intent,
            type=base_result.type,
            amount=base_result.amount,
            category=base_result.category,
            description=base_result.description,
            transaction_date=base_result.transaction_date,
            source=source,
            confidence=base_result.confidence,
            need_confirmation=False,
            reasons=base_result.reasons,
            period=base_result.period,
            limit=getattr(base_result, "limit", None),
            sort_order=getattr(base_result, "sort_order", None),
            category_filter=getattr(base_result, "category_filter", None),
        )

    category, category_confidence, category_source, reasons = _resolve_category(
        text=text,
        base_result=base_result,
    )
    confidence = _calculate_final_confidence(
        base_result=base_result,
        category=category,
        category_confidence=category_confidence,
        category_source=category_source,
    )
    need_confirmation = (
        confidence < AUTO_SAVE_CONFIDENCE
        or base_result.amount is None
        or base_result.type is None
        or category is None
        or category_source == "fallback"
    )

    return ParsedMessage(
        intent=base_result.intent,
        type=base_result.type,
        amount=base_result.amount,
        category=category,
        description=base_result.description,
        transaction_date=base_result.transaction_date,
        source=source,
        confidence=confidence,
        need_confirmation=need_confirmation,
        reasons=reasons,
        period=base_result.period,
        category_confidence=category_confidence,
        category_source=category_source,
    )


def _resolve_category(
    *,
    text: str,
    base_result: ParsedTransactionText,
) -> tuple[str | None, float | None, str | None, list[str]]:
    reasons = list(base_result.reasons)
    has_rule_fallback = "category_fallback" in reasons
    model_prediction = predict_category(
        base_result.description or text,
        transaction_type=base_result.type,
    )

    if _should_use_model_category(
        model_prediction=model_prediction,
        has_rule_fallback=has_rule_fallback,
    ):
        reasons = [reason for reason in reasons if reason != "category_fallback"]
        return (
            model_prediction.category,
            model_prediction.confidence,
            model_prediction.source,
            reasons,
        )

    if base_result.category:
        category_source = "fallback" if has_rule_fallback else "rule"
        category_confidence = 0.35 if has_rule_fallback else 0.95
        return base_result.category, category_confidence, category_source, reasons

    return None, None, None, reasons


def _should_use_model_category(
    *,
    model_prediction: CategoryPrediction | None,
    has_rule_fallback: bool,
) -> bool:
    if model_prediction is None:
        return False
    if model_prediction.category == "Lainnya":
        return False
    if not has_rule_fallback:
        return False
    return model_prediction.confidence >= CATEGORY_MODEL_MIN_CONFIDENCE


def _calculate_final_confidence(
    *,
    base_result: ParsedTransactionText,
    category: str | None,
    category_confidence: float | None,
    category_source: str | None,
) -> float:
    if base_result.intent != INTENT_ADD_TRANSACTION:
        return round(base_result.confidence, 4)

    confidence = 0.05
    if base_result.amount is not None:
        confidence += 0.35
    if base_result.type:
        confidence += 0.20
    if category and category_source != "fallback":
        confidence += 0.20 * min(category_confidence or 0.0, 1.0)
    if base_result.description:
        confidence += 0.10
    if base_result.transaction_date:
        confidence += 0.10

    return round(min(max(confidence, 0.0), 1.0), 4)
