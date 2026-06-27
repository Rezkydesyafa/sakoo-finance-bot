import hashlib
import hmac
import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import BotLog, UserPlatformAccount
from app.modules.transactions.service import (
    TextTransactionResult,
    handle_whatsapp_text_transaction,
)
from app.modules.waha.client import WahaClient, WahaClientError, get_waha_client
from app.modules.waha.linking import handle_account_linking
from app.modules.waha.parser import parse_waha_message, whatsapp_identifier_candidates


router = APIRouter(prefix="/webhook", tags=["webhook"])


class WahaWebhookResponse(BaseModel):
    status: str
    message_type: str
    bot_log_id: int
    user_id: int | None
    linking_status: str | None = None
    transaction_status: str | None = None
    transaction_id: int | None = None
    reply_status: str | None = None


@router.post("/waha", response_model=WahaWebhookResponse)
async def receive_waha_webhook(
    request: Request,
    x_webhook_hmac: str | None = Header(default=None),
    x_webhook_hmac_algorithm: str | None = Header(default=None),
    db: Session = Depends(get_db),
    waha_client: WahaClient = Depends(get_waha_client),
) -> WahaWebhookResponse:
    raw_body = await request.body()
    _verify_webhook_signature(raw_body, x_webhook_hmac, x_webhook_hmac_algorithm)

    try:
        body = json.loads(raw_body.decode("utf-8") or "{}")
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        ) from exc

    if not isinstance(body, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webhook payload must be an object.",
        )

    parsed = parse_waha_message(body)
    user_id = _resolve_whatsapp_user_id(db, parsed)
    linking_result = handle_account_linking(
        db=db,
        parsed=parsed,
        current_user_id=user_id,
    )
    transaction_result = _handle_text_transaction_if_needed(
        db=db,
        parsed_message_type=parsed.message_type,
        parsed_text=parsed.text,
        linking_action=linking_result.action,
        linked_user_id=linking_result.user_id or user_id,
    )
    reply_text = transaction_result.reply_text if transaction_result else linking_result.reply_text
    bot_log = BotLog(
        user_id=linking_result.user_id or user_id,
        platform="whatsapp",
        message_type="command" if linking_result.action == "link" else parsed.message_type,
        raw_message=parsed.text,
        parsed_result={
            **parsed.to_log_payload(),
            "linking": linking_result.to_log_payload(),
            "transaction": transaction_result.to_log_payload()
            if transaction_result
            else None,
        },
        status=_resolve_bot_log_status(linking_result.status, transaction_result),
        error_message=transaction_result.error_message
        if transaction_result
        else linking_result.error_message,
    )
    db.add(bot_log)
    db.commit()
    db.refresh(bot_log)

    reply_status = _send_reply_if_needed(
        db=db,
        client=waha_client,
        parsed_chat_id=parsed.chat_id,
        reply_text=reply_text,
        bot_log=bot_log,
    )

    return WahaWebhookResponse(
        status="ok",
        message_type=bot_log.message_type,
        bot_log_id=bot_log.id,
        user_id=bot_log.user_id,
        linking_status=linking_result.status,
        transaction_status=transaction_result.status if transaction_result else None,
        transaction_id=transaction_result.transaction_id if transaction_result else None,
        reply_status=reply_status,
    )


def _resolve_whatsapp_user_id(db: Session, parsed: Any) -> int | None:
    candidates = whatsapp_identifier_candidates(parsed)
    if not candidates:
        return None

    account = db.scalar(
        select(UserPlatformAccount).where(
            UserPlatformAccount.platform == "whatsapp",
            UserPlatformAccount.is_active.is_(True),
            (
                UserPlatformAccount.platform_user_id.in_(candidates)
                | UserPlatformAccount.chat_id.in_(candidates)
                | UserPlatformAccount.phone_number.in_(candidates)
            ),
        )
    )
    return account.user_id if account else None


def _handle_text_transaction_if_needed(
    *,
    db: Session,
    parsed_message_type: str,
    parsed_text: str | None,
    linking_action: str,
    linked_user_id: int | None,
) -> TextTransactionResult | None:
    if linking_action != "ignored" or not linked_user_id:
        return None
    if parsed_message_type != "text" or not parsed_text:
        return None
    return handle_whatsapp_text_transaction(
        db=db,
        user_id=linked_user_id,
        text=parsed_text,
    )


def _resolve_bot_log_status(
    linking_status: str,
    transaction_result: TextTransactionResult | None,
) -> str:
    if transaction_result:
        return f"transaction_{transaction_result.status}"
    if linking_status == "success":
        return "linked"
    return "received"


def _send_reply_if_needed(
    *,
    db: Session,
    client: WahaClient,
    parsed_chat_id: str | None,
    reply_text: str | None,
    bot_log: BotLog,
) -> str | None:
    if not reply_text:
        return None
    if not parsed_chat_id:
        bot_log.status = "reply_failed"
        bot_log.error_message = _append_error(bot_log.error_message, "missing_chat_id")
        db.commit()
        return "failed"

    try:
        client.send_text(chat_id=parsed_chat_id, text=reply_text)
    except WahaClientError as exc:
        bot_log.status = "reply_failed"
        bot_log.error_message = _append_error(bot_log.error_message, str(exc))
        db.commit()
        return "failed"

    return "sent"


def _append_error(existing: str | None, new_error: str) -> str:
    return f"{existing}; {new_error}" if existing else new_error


def _verify_webhook_signature(
    raw_body: bytes,
    signature: str | None,
    algorithm: str | None,
) -> None:
    settings = get_settings()
    secret = settings.waha_webhook_hmac_key
    if not secret:
        return

    if (algorithm or "").lower() != "sha512" or not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid WAHA webhook signature.",
        )

    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid WAHA webhook signature.",
        )
