import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import BotLog, UserPlatformAccount
from app.modules.telegram.client import (
    TelegramClient,
    TelegramClientError,
    get_telegram_client,
)
from app.modules.telegram.linking import handle_telegram_account_linking
from app.modules.telegram.parser import (
    parse_telegram_update,
    telegram_identifier_candidates,
)
from app.modules.transactions.service import (
    TextTransactionResult,
    handle_telegram_text_transaction,
)


router = APIRouter(prefix="/webhook", tags=["webhook"])


class TelegramWebhookResponse(BaseModel):
    status: str
    message_type: str
    bot_log_id: int
    user_id: int | None
    linking_status: str | None = None
    transaction_status: str | None = None
    transaction_id: int | None = None
    reply_status: str | None = None


@router.post("/telegram", response_model=TelegramWebhookResponse)
async def receive_telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(
        default=None,
        alias="X-Telegram-Bot-Api-Secret-Token",
    ),
    db: Session = Depends(get_db),
    telegram_client: TelegramClient = Depends(get_telegram_client),
) -> TelegramWebhookResponse:
    _verify_webhook_secret(x_telegram_bot_api_secret_token)

    raw_body = await request.body()
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
            detail="Telegram update payload must be an object.",
        )

    try:
        parsed = parse_telegram_update(body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Telegram update: {exc}",
        ) from exc

    user_id = _resolve_telegram_user_id(db, parsed)
    linking_result = handle_telegram_account_linking(
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
        platform="telegram",
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
        client=telegram_client,
        chat_id=parsed.chat_id,
        reply_text=reply_text,
        bot_log=bot_log,
    )

    return TelegramWebhookResponse(
        status="ok",
        message_type=bot_log.message_type,
        bot_log_id=bot_log.id,
        user_id=bot_log.user_id,
        linking_status=linking_result.status,
        transaction_status=transaction_result.status if transaction_result else None,
        transaction_id=transaction_result.transaction_id if transaction_result else None,
        reply_status=reply_status,
    )


def _resolve_telegram_user_id(db: Session, parsed: Any) -> int | None:
    candidates = telegram_identifier_candidates(parsed)
    if not candidates:
        return None

    account = db.scalar(
        select(UserPlatformAccount).where(
            UserPlatformAccount.platform == "telegram",
            UserPlatformAccount.is_active.is_(True),
            (
                UserPlatformAccount.platform_user_id.in_(candidates)
                | UserPlatformAccount.chat_id.in_(candidates)
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
    return handle_telegram_text_transaction(
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
    client: TelegramClient,
    chat_id: str | None,
    reply_text: str | None,
    bot_log: BotLog,
) -> str | None:
    if not reply_text:
        return None
    if not chat_id:
        bot_log.status = "reply_failed"
        bot_log.error_message = _append_error(bot_log.error_message, "missing_chat_id")
        db.commit()
        return "failed"

    try:
        client.send_message(chat_id=chat_id, text=reply_text)
    except TelegramClientError as exc:
        bot_log.status = "reply_failed"
        bot_log.error_message = _append_error(bot_log.error_message, str(exc))
        db.commit()
        return "failed"

    return "sent"


def _verify_webhook_secret(secret_header: str | None) -> None:
    expected_secret = get_settings().telegram_webhook_secret
    if not expected_secret:
        return
    if secret_header != expected_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram webhook secret.",
        )


def _append_error(existing: str | None, new_error: str) -> str:
    return f"{existing}; {new_error}" if existing else new_error
