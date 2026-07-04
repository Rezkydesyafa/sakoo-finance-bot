from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BotLog
from app.modules.parser.service import ParsedMessage


CONVERSATION_MESSAGE_TYPE = "conversation_state"
PENDING_TRANSACTION_STATUS = "pending_transaction"
CONFIRMED_TRANSACTION_STATUS = "confirmed_transaction"
CANCELLED_TRANSACTION_STATUS = "cancelled_transaction"
EDITED_TRANSACTION_STATUS = "edited_transaction"
EXPIRED_TRANSACTION_STATUS = "expired_transaction"
# ponytail: fixed chat confirmation TTL; make configurable only if channel SLAs differ.
PENDING_TRANSACTION_TTL = timedelta(minutes=30)


def store_pending_transaction(
    db: Session,
    *,
    user_id: int,
    platform: str,
    raw_message: str,
    parse_result: ParsedMessage,
) -> BotLog:
    pending_log = BotLog(
        user_id=user_id,
        platform=platform,
        message_type=CONVERSATION_MESSAGE_TYPE,
        raw_message=raw_message,
        parsed_result={
            "kind": "transaction_confirmation",
            "parse_result": parse_result.to_log_payload(),
        },
        status=PENDING_TRANSACTION_STATUS,
    )
    db.add(pending_log)
    db.flush()
    return pending_log


def get_pending_transaction(db: Session, *, user_id: int) -> tuple[BotLog, ParsedMessage] | None:
    pending_log = db.scalar(
        select(BotLog)
        .where(
            BotLog.user_id == user_id,
            BotLog.message_type == CONVERSATION_MESSAGE_TYPE,
            BotLog.status == PENDING_TRANSACTION_STATUS,
        )
        .order_by(BotLog.created_at.desc(), BotLog.id.desc())
    )
    if pending_log is None:
        return None
    if _is_pending_expired(pending_log.created_at):
        pending_log.status = EXPIRED_TRANSACTION_STATUS
        db.flush()
        return None

    payload = pending_log.parsed_result or {}
    parse_payload = payload.get("parse_result") if isinstance(payload, dict) else None
    if not isinstance(parse_payload, dict):
        pending_log.status = EXPIRED_TRANSACTION_STATUS
        db.flush()
        return None

    return pending_log, parsed_message_from_payload(parse_payload)


def update_pending_transaction(
    db: Session,
    *,
    pending_log: BotLog,
    parse_result: ParsedMessage,
    raw_message: str,
) -> None:
    payload = dict(pending_log.parsed_result or {})
    payload["parse_result"] = parse_result.to_log_payload()
    payload["last_edit_message"] = raw_message
    pending_log.parsed_result = payload
    pending_log.status = PENDING_TRANSACTION_STATUS
    db.flush()


def mark_pending_status(db: Session, *, pending_log: BotLog, status: str) -> None:
    pending_log.status = status
    db.flush()


def parsed_message_from_payload(payload: dict[str, Any]) -> ParsedMessage:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    raw_date = payload.get("transaction_date")
    return ParsedMessage(
        intent=str(payload.get("intent") or "unknown"),
        type=payload.get("type"),
        amount=_decimal_or_none(payload.get("amount")),
        category=payload.get("category"),
        description=payload.get("description"),
        transaction_date=date.fromisoformat(raw_date) if raw_date else None,
        source=str(payload.get("source") or "whatsapp_text"),
        confidence=float(payload.get("confidence") or 0),
        need_confirmation=bool(payload.get("need_confirmation")),
        reasons=list(payload.get("reasons") or []),
        period=payload.get("period"),
        category_confidence=metadata.get("category_confidence"),
        category_source=metadata.get("category_source"),
    )


def clone_parsed_message(
    parse_result: ParsedMessage,
    **updates: Any,
) -> ParsedMessage:
    values = {
        "intent": parse_result.intent,
        "type": parse_result.type,
        "amount": parse_result.amount,
        "category": parse_result.category,
        "description": parse_result.description,
        "transaction_date": parse_result.transaction_date,
        "source": parse_result.source,
        "confidence": parse_result.confidence,
        "need_confirmation": parse_result.need_confirmation,
        "reasons": list(parse_result.reasons),
        "period": parse_result.period,
        "category_confidence": parse_result.category_confidence,
        "category_source": parse_result.category_source,
    }
    values.update(updates)
    return ParsedMessage(**values)


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _is_pending_expired(created_at: datetime) -> bool:
    value = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - value > PENDING_TRANSACTION_TTL
