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
from app.modules.ocr.client import OcrClient, get_ocr_client
from app.modules.transactions.service import (
    TextTransactionResult,
    handle_whatsapp_text_transaction,
)
from app.modules.waha.client import WahaClient, WahaClientError, get_waha_client
from app.modules.waha.linking import handle_account_linking
from app.modules.waha.parser import parse_waha_message, whatsapp_identifier_candidates
from app.modules.waha.receipt_ocr import (
    ReceiptOcrFlowResult,
    handle_whatsapp_receipt_confirmation,
    handle_whatsapp_receipt_image,
)


router = APIRouter(prefix="/webhook", tags=["webhook"])


class WahaWebhookResponse(BaseModel):
    status: str
    message_type: str
    bot_log_id: int
    user_id: int | None
    linking_status: str | None = None
    transaction_status: str | None = None
    transaction_id: int | None = None
    receipt_id: int | None = None
    job_id: int | None = None
    reply_status: str | None = None


@router.post("/waha", response_model=WahaWebhookResponse)
async def receive_waha_webhook(
    request: Request,
    x_webhook_hmac: str | None = Header(default=None),
    x_webhook_hmac_algorithm: str | None = Header(default=None),
    db: Session = Depends(get_db),
    waha_client: WahaClient = Depends(get_waha_client),
    ocr_client: OcrClient = Depends(get_ocr_client),
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
    linked_user_id = linking_result.user_id or user_id
    receipt_result = _handle_receipt_ocr_if_needed(
        db=db,
        parsed=parsed,
        linking_action=linking_result.action,
        linked_user_id=linked_user_id,
        waha_client=waha_client,
        ocr_client=ocr_client,
    )
    transaction_result = None
    if receipt_result is None:
        transaction_result = _handle_text_transaction_if_needed(
            db=db,
            parsed_message_type=parsed.message_type,
            parsed_text=parsed.text,
            linking_action=linking_result.action,
            linked_user_id=linked_user_id,
        )
    reply_text = _resolve_reply_text(
        receipt_result=receipt_result,
        transaction_result=transaction_result,
        linking_reply_text=linking_result.reply_text,
    )
    bot_log = BotLog(
        user_id=linked_user_id,
        platform="whatsapp",
        message_type=_resolve_bot_log_message_type(
            parsed_message_type=parsed.message_type,
            linking_action=linking_result.action,
            receipt_result=receipt_result,
        ),
        raw_message=parsed.text,
        parsed_result={
            **parsed.to_log_payload(),
            "linking": linking_result.to_log_payload(),
            "receipt_ocr": receipt_result.to_log_payload() if receipt_result else None,
            "transaction": transaction_result.to_log_payload()
            if transaction_result
            else None,
        },
        status=_resolve_bot_log_status(
            linking_status=linking_result.status,
            receipt_result=receipt_result,
            transaction_result=transaction_result,
        ),
        error_message=_resolve_error_message(
            linking_error=linking_result.error_message,
            receipt_result=receipt_result,
            transaction_result=transaction_result,
        ),
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
        transaction_status=_resolve_response_transaction_status(
            receipt_result,
            transaction_result,
        ),
        transaction_id=_resolve_response_transaction_id(receipt_result, transaction_result),
        receipt_id=receipt_result.receipt_id if receipt_result else None,
        job_id=receipt_result.job_id if receipt_result else None,
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


def _handle_receipt_ocr_if_needed(
    *,
    db: Session,
    parsed: Any,
    linking_action: str,
    linked_user_id: int | None,
    waha_client: WahaClient,
    ocr_client: OcrClient,
) -> ReceiptOcrFlowResult | None:
    if linking_action != "ignored" or not linked_user_id:
        return None

    if parsed.message_type == "image":
        return handle_whatsapp_receipt_image(
            db=db,
            user_id=linked_user_id,
            parsed=parsed,
            waha_client=waha_client,
            ocr_client=ocr_client,
        )

    if parsed.message_type == "text":
        return handle_whatsapp_receipt_confirmation(
            db=db,
            user_id=linked_user_id,
            text=parsed.text,
        )

    return None


def _resolve_reply_text(
    *,
    receipt_result: ReceiptOcrFlowResult | None,
    transaction_result: TextTransactionResult | None,
    linking_reply_text: str | None,
) -> str | None:
    if receipt_result:
        return receipt_result.reply_text
    if transaction_result:
        return transaction_result.reply_text
    return linking_reply_text


def _resolve_bot_log_message_type(
    *,
    parsed_message_type: str,
    linking_action: str,
    receipt_result: ReceiptOcrFlowResult | None,
) -> str:
    if receipt_result:
        return "receipt_ocr"
    if linking_action == "link":
        return "command"
    return parsed_message_type


def _resolve_bot_log_status(
    linking_status: str,
    receipt_result: ReceiptOcrFlowResult | None,
    transaction_result: TextTransactionResult | None,
) -> str:
    if receipt_result:
        return f"receipt_ocr_{receipt_result.status}"
    if transaction_result:
        return f"transaction_{transaction_result.status}"
    if linking_status == "success":
        return "linked"
    return "received"


def _resolve_error_message(
    *,
    linking_error: str | None,
    receipt_result: ReceiptOcrFlowResult | None,
    transaction_result: TextTransactionResult | None,
) -> str | None:
    if receipt_result and receipt_result.error_message:
        return receipt_result.error_message
    if transaction_result and transaction_result.error_message:
        return transaction_result.error_message
    return linking_error


def _resolve_response_transaction_status(
    receipt_result: ReceiptOcrFlowResult | None,
    transaction_result: TextTransactionResult | None,
) -> str | None:
    if receipt_result:
        return receipt_result.status
    return transaction_result.status if transaction_result else None


def _resolve_response_transaction_id(
    receipt_result: ReceiptOcrFlowResult | None,
    transaction_result: TextTransactionResult | None,
) -> int | None:
    if receipt_result and receipt_result.transaction_id:
        return receipt_result.transaction_id
    return transaction_result.transaction_id if transaction_result else None


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
