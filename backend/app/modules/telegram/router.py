import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import BotLog, UserPlatformAccount
from app.modules.jobs.service import (
    JobQueueError,
    ReceiptOcrEnqueue,
    ReportPdfEnqueue,
    VoiceSttEnqueue,
    get_receipt_ocr_enqueue,
    get_report_pdf_enqueue,
    get_voice_stt_enqueue,
    queue_report_pdf_job,
)
from app.modules.reports.bot_pdf import ReportPdfFlowResult, handle_report_pdf_command
from app.modules.stt.flow import VoiceSttFlowResult
from app.modules.telegram.client import (
    TelegramClient,
    TelegramClientError,
    get_telegram_client,
)
from app.modules.bot.response_templates import format_help_response
from app.modules.telegram.callback_handler import (
    WAITING_EXPENSE_INPUT,
    WAITING_INCOME_INPUT,
    build_welcome_text,
    consume_waiting_input_state,
    handle_callback_query,
)
from app.modules.telegram.linking import handle_telegram_account_linking
from app.modules.telegram.menu import build_main_menu
from app.modules.telegram.parser import (
    parse_telegram_update,
    telegram_identifier_candidates,
)
from app.modules.telegram.receipt_ocr import (
    TelegramReceiptOcrFlowResult,
    handle_telegram_receipt_photo,
    handle_telegram_receipt_text,
)
from app.modules.telegram.voice_stt import handle_telegram_voice_note
from app.modules.transactions.service import (
    TextTransactionResult,
    build_balance_response,
    build_recent_transactions_response,
    build_report_summary_response,
    build_transaction_list_response,
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
    voice_note_id: int | None = None
    job_id: int | None = None
    reply_status: str | None = None


@dataclass(frozen=True)
class TelegramMenuCommandResult:
    status: str
    reply_text: str
    reply_markup: dict[str, Any] | None = None
    transaction_status: str | None = None
    job_id: int | None = None
    error_message: str | None = None

    def to_log_payload(self) -> dict[str, Any]:
        return asdict(self)


@router.post("/telegram", response_model=TelegramWebhookResponse)
async def receive_telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(
        default=None,
        alias="X-Telegram-Bot-Api-Secret-Token",
    ),
    db: Session = Depends(get_db),
    telegram_client: TelegramClient = Depends(get_telegram_client),
    receipt_enqueue: ReceiptOcrEnqueue = Depends(get_receipt_ocr_enqueue),
    stt_enqueue: VoiceSttEnqueue = Depends(get_voice_stt_enqueue),
    pdf_enqueue: ReportPdfEnqueue = Depends(get_report_pdf_enqueue),
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
    menu_command_result = _handle_menu_command_if_needed(
        parsed,
        db=db,
        linked_user_id=user_id,
        enqueue=pdf_enqueue,
    )
    if menu_command_result is not None:
        bot_log = BotLog(
            user_id=user_id,
            platform="telegram",
            message_type="command",
            raw_message=parsed.text,
            parsed_result={
                **parsed.to_log_payload(),
                "menu_command": menu_command_result.to_log_payload(),
            },
            status=f"menu_{menu_command_result.status}",
            error_message=menu_command_result.error_message,
        )
        db.add(bot_log)
        db.commit()
        db.refresh(bot_log)

        reply_status = _send_reply_if_needed(
            db=db,
            client=telegram_client,
            chat_id=parsed.chat_id,
            reply_text=menu_command_result.reply_text,
            bot_log=bot_log,
            reply_markup=menu_command_result.reply_markup,
        )
        return TelegramWebhookResponse(
            status="ok",
            message_type=bot_log.message_type,
            bot_log_id=bot_log.id,
            user_id=bot_log.user_id,
            linking_status="linked" if user_id else "unlinked",
            transaction_status=(
                menu_command_result.transaction_status
                or menu_command_result.status
            ),
            job_id=menu_command_result.job_id,
            reply_status=reply_status,
        )

    if parsed.message_type == "callback_query":
        callback_result = handle_callback_query(
            db=db,
            parsed=parsed,
            linked_user_id=user_id,
            telegram_client=telegram_client,
            enqueue=pdf_enqueue,
        )
        bot_log = BotLog(
            user_id=user_id,
            platform="telegram",
            message_type="callback_query",
            raw_message=parsed.callback_data,
            parsed_result={
                **parsed.to_log_payload(),
                "callback": callback_result.to_log_payload(),
            },
            status=f"callback_{callback_result.status}",
            error_message=callback_result.error_message,
        )
        db.add(bot_log)
        db.commit()
        db.refresh(bot_log)

        return TelegramWebhookResponse(
            status="ok",
            message_type=bot_log.message_type,
            bot_log_id=bot_log.id,
            user_id=bot_log.user_id,
            linking_status="linked" if user_id else "unlinked",
            transaction_status=callback_result.transaction_status or callback_result.status,
            job_id=callback_result.job_id,
            reply_status=callback_result.reply_status,
        )

    linking_result = handle_telegram_account_linking(
        db=db,
        parsed=parsed,
        current_user_id=user_id,
    )
    linked_user_id = linking_result.user_id or user_id
    voice_result = _handle_voice_stt_if_needed(
        db=db,
        parsed=parsed,
        linking_action=linking_result.action,
        linked_user_id=linked_user_id,
        telegram_client=telegram_client,
        enqueue=stt_enqueue,
    )
    receipt_result = None
    if voice_result is None:
        receipt_result = _handle_receipt_ocr_if_needed(
            db=db,
            parsed=parsed,
            linking_action=linking_result.action,
            linked_user_id=linked_user_id,
            telegram_client=telegram_client,
            enqueue=receipt_enqueue,
        )
    if voice_result is None and receipt_result is None:
        receipt_result = _handle_receipt_text_if_needed(
            db=db,
            parsed=parsed,
            linking_action=linking_result.action,
            linked_user_id=linked_user_id,
        )
    report_pdf_result = None
    if voice_result is None and receipt_result is None:
        report_pdf_result = _handle_report_pdf_if_needed(
            db=db,
            parsed=parsed,
            linking_action=linking_result.action,
            linked_user_id=linked_user_id,
            enqueue=pdf_enqueue,
        )
    transaction_result = None
    if voice_result is None and receipt_result is None and report_pdf_result is None:
        transaction_result = _handle_text_transaction_if_needed(
            db=db,
            parsed_message_type=parsed.message_type,
            parsed_text=parsed.text,
            linking_action=linking_result.action,
            linked_user_id=linked_user_id,
        )
    reply_text = _resolve_reply_text(
        voice_result=voice_result,
        receipt_result=receipt_result,
        report_pdf_result=report_pdf_result,
        transaction_result=transaction_result,
        linking_reply_text=linking_result.reply_text,
    )

    bot_log = BotLog(
        user_id=linked_user_id,
        platform="telegram",
        message_type=_resolve_bot_log_message_type(
            parsed_message_type=parsed.message_type,
            linking_action=linking_result.action,
            voice_result=voice_result,
            receipt_result=receipt_result,
            report_pdf_result=report_pdf_result,
        ),
        raw_message=parsed.text,
        parsed_result={
            **parsed.to_log_payload(),
            "linking": linking_result.to_log_payload(),
            "voice_stt": voice_result.to_log_payload() if voice_result else None,
            "receipt_ocr": receipt_result.to_log_payload()
            if receipt_result
            else None,
            "report_pdf": report_pdf_result.to_log_payload()
            if report_pdf_result
            else None,
            "transaction": transaction_result.to_log_payload()
            if transaction_result
            else None,
        },
        status=_resolve_bot_log_status(
            linking_result.status,
            voice_result,
            receipt_result,
            report_pdf_result,
            transaction_result,
        ),
        error_message=_resolve_error_message(
            linking_result.error_message,
            voice_result,
            receipt_result,
            report_pdf_result,
            transaction_result,
        ),
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
        transaction_status=_resolve_response_transaction_status(
            voice_result,
            receipt_result,
            report_pdf_result,
            transaction_result,
        ),
        transaction_id=_resolve_response_transaction_id(
            voice_result,
            transaction_result,
        ),
        voice_note_id=voice_result.voice_note_id if voice_result else None,
        job_id=_resolve_response_job_id(voice_result, receipt_result, report_pdf_result),
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
    waiting_state = _consume_waiting_state_for_text(
        db=db,
        user_id=linked_user_id,
        text=parsed_text,
    )
    return handle_telegram_text_transaction(
        db=db,
        user_id=linked_user_id,
        text=parsed_text,
        forced_transaction_type=_forced_type_from_waiting_state(waiting_state),
    )


def _handle_voice_stt_if_needed(
    *,
    db: Session,
    parsed: Any,
    linking_action: str,
    linked_user_id: int | None,
    telegram_client: TelegramClient,
    enqueue: VoiceSttEnqueue,
) -> VoiceSttFlowResult | None:
    if linking_action != "ignored" or not linked_user_id:
        return None

    if parsed.message_type == "audio":
        return handle_telegram_voice_note(
            db=db,
            user_id=linked_user_id,
            parsed=parsed,
            telegram_client=telegram_client,
            enqueue=enqueue,
        )

    return None


def _handle_receipt_ocr_if_needed(
    *,
    db: Session,
    parsed: Any,
    linking_action: str,
    linked_user_id: int | None,
    telegram_client: TelegramClient,
    enqueue: ReceiptOcrEnqueue,
) -> TelegramReceiptOcrFlowResult | None:
    if linking_action != "ignored" or not linked_user_id:
        return None

    return handle_telegram_receipt_photo(
        db=db,
        user_id=linked_user_id,
        parsed=parsed,
        telegram_client=telegram_client,
        enqueue=enqueue,
    )


def _handle_receipt_text_if_needed(
    *,
    db: Session,
    parsed: Any,
    linking_action: str,
    linked_user_id: int | None,
) -> TelegramReceiptOcrFlowResult | None:
    if linking_action != "ignored" or not linked_user_id:
        return None
    if parsed.message_type != "text" or not parsed.text:
        return None
    return handle_telegram_receipt_text(
        db=db,
        user_id=linked_user_id,
        text=parsed.text,
    )


def _handle_report_pdf_if_needed(
    *,
    db: Session,
    parsed: Any,
    linking_action: str,
    linked_user_id: int | None,
    enqueue: ReportPdfEnqueue,
) -> ReportPdfFlowResult | None:
    if linking_action != "ignored" or not linked_user_id:
        return None
    if parsed.message_type != "text" or not parsed.text:
        return None

    return handle_report_pdf_command(
        db=db,
        user_id=linked_user_id,
        text=parsed.text,
        platform="telegram",
        enqueue=enqueue,
        notify_chat_id=parsed.chat_id,
    )


def _resolve_reply_text(
    *,
    voice_result: VoiceSttFlowResult | None,
    receipt_result: TelegramReceiptOcrFlowResult | None,
    report_pdf_result: ReportPdfFlowResult | None,
    transaction_result: TextTransactionResult | None,
    linking_reply_text: str | None,
) -> str | None:
    if voice_result:
        return voice_result.reply_text
    if receipt_result:
        return receipt_result.reply_text
    if report_pdf_result:
        return report_pdf_result.reply_text
    if transaction_result:
        return transaction_result.reply_text
    return linking_reply_text


def _resolve_bot_log_message_type(
    *,
    parsed_message_type: str,
    linking_action: str,
    voice_result: VoiceSttFlowResult | None,
    receipt_result: TelegramReceiptOcrFlowResult | None,
    report_pdf_result: ReportPdfFlowResult | None,
) -> str:
    if voice_result:
        return "voice_stt"
    if receipt_result:
        return "receipt_ocr"
    if report_pdf_result:
        return "report_pdf"
    if linking_action == "link":
        return "command"
    return parsed_message_type


def _resolve_bot_log_status(
    linking_status: str,
    voice_result: VoiceSttFlowResult | None,
    receipt_result: TelegramReceiptOcrFlowResult | None,
    report_pdf_result: ReportPdfFlowResult | None,
    transaction_result: TextTransactionResult | None,
) -> str:
    if voice_result:
        return f"voice_stt_{voice_result.status}"
    if receipt_result:
        return f"receipt_ocr_{receipt_result.status}"
    if report_pdf_result:
        return f"report_pdf_{report_pdf_result.status}"
    if transaction_result:
        return f"transaction_{transaction_result.status}"
    if linking_status == "success":
        return "linked"
    return "received"


def _resolve_error_message(
    linking_error: str | None,
    voice_result: VoiceSttFlowResult | None,
    receipt_result: TelegramReceiptOcrFlowResult | None,
    report_pdf_result: ReportPdfFlowResult | None,
    transaction_result: TextTransactionResult | None,
) -> str | None:
    if voice_result and voice_result.error_message:
        return voice_result.error_message
    if receipt_result and receipt_result.error_message:
        return receipt_result.error_message
    if report_pdf_result and report_pdf_result.error_message:
        return report_pdf_result.error_message
    if transaction_result and transaction_result.error_message:
        return transaction_result.error_message
    return linking_error


def _resolve_response_transaction_status(
    voice_result: VoiceSttFlowResult | None,
    receipt_result: TelegramReceiptOcrFlowResult | None,
    report_pdf_result: ReportPdfFlowResult | None,
    transaction_result: TextTransactionResult | None,
) -> str | None:
    if voice_result:
        return voice_result.status
    if receipt_result:
        return receipt_result.status
    if report_pdf_result:
        return report_pdf_result.status
    return transaction_result.status if transaction_result else None


def _resolve_response_transaction_id(
    voice_result: VoiceSttFlowResult | None,
    transaction_result: TextTransactionResult | None,
) -> int | None:
    if voice_result and voice_result.transaction_id:
        return voice_result.transaction_id
    return transaction_result.transaction_id if transaction_result else None


def _resolve_response_job_id(
    voice_result: VoiceSttFlowResult | None,
    receipt_result: TelegramReceiptOcrFlowResult | None,
    report_pdf_result: ReportPdfFlowResult | None,
) -> int | None:
    if voice_result and voice_result.job_id:
        return voice_result.job_id
    if receipt_result and receipt_result.job_id:
        return receipt_result.job_id
    if report_pdf_result and report_pdf_result.job_id:
        return report_pdf_result.job_id
    return None


def _send_reply_if_needed(
    *,
    db: Session,
    client: TelegramClient,
    chat_id: str | None,
    reply_text: str | None,
    bot_log: BotLog,
    reply_markup: dict[str, Any] | None = None,
) -> str | None:
    if not reply_text:
        return None
    if not chat_id:
        bot_log.status = "reply_failed"
        bot_log.error_message = _append_error(bot_log.error_message, "missing_chat_id")
        db.commit()
        return "failed"

    try:
        message_kwargs: dict[str, Any] = {"chat_id": chat_id, "text": reply_text}
        if reply_markup:
            message_kwargs["reply_markup"] = reply_markup
        client.send_message(**message_kwargs)
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


def _handle_menu_command_if_needed(
    parsed: Any,
    *,
    db: Session,
    linked_user_id: int | None,
    enqueue: ReportPdfEnqueue,
) -> TelegramMenuCommandResult | None:
    if parsed.message_type != "text" or not parsed.text:
        return None

    command = parsed.text.strip().split(maxsplit=1)[0].lower().split("@", 1)[0]
    if command == "/start":
        return TelegramMenuCommandResult(
            status="start",
            reply_text=build_welcome_text(),
            reply_markup=build_main_menu(),
        )
    if command == "/help":
        return TelegramMenuCommandResult(
            status="help",
            reply_text=format_help_response(),
            reply_markup=build_main_menu(),
        )
    if command not in {
        "/saldo",
        "/pengeluaran",
        "/pemasukan",
        "/laporan",
        "/export",
        "/riwayat",
    }:
        return None

    if linked_user_id is None:
        return TelegramMenuCommandResult(
            status="unlinked",
            reply_text=_link_instruction_text(),
            reply_markup=build_main_menu(),
        )

    if command == "/saldo":
        return TelegramMenuCommandResult(
            status="balance",
            transaction_status="balance",
            reply_text=build_balance_response(db, linked_user_id),
            reply_markup=build_main_menu(),
        )
    if command == "/pengeluaran":
        return TelegramMenuCommandResult(
            status="expense_list",
            transaction_status="expense_list",
            reply_text=build_transaction_list_response(
                db,
                linked_user_id,
                transaction_type="expense",
                period=None,
            ),
            reply_markup=build_main_menu(),
        )
    if command == "/pemasukan":
        return TelegramMenuCommandResult(
            status="income_list",
            transaction_status="income_list",
            reply_text=build_transaction_list_response(
                db,
                linked_user_id,
                transaction_type="income",
                period=None,
            ),
            reply_markup=build_main_menu(),
        )
    if command == "/laporan":
        return TelegramMenuCommandResult(
            status="report_month",
            transaction_status="report",
            reply_text=build_report_summary_response(db, linked_user_id, "month"),
            reply_markup=build_main_menu(),
        )
    if command == "/riwayat":
        return TelegramMenuCommandResult(
            status="history",
            transaction_status="history",
            reply_text=build_recent_transactions_response(db, linked_user_id),
            reply_markup=build_main_menu(),
        )
    if command == "/export":
        return _handle_export_command(
            db=db,
            parsed=parsed,
            linked_user_id=linked_user_id,
            enqueue=enqueue,
        )
    return None


def _handle_export_command(
    *,
    db: Session,
    parsed: Any,
    linked_user_id: int,
    enqueue: ReportPdfEnqueue,
) -> TelegramMenuCommandResult:
    try:
        job = queue_report_pdf_job(
            db,
            user_id=linked_user_id,
            period="month",
            anchor_date=date.today(),
            source="telegram_bot",
            enqueue=enqueue,
            notify_chat_id=parsed.chat_id,
            notify_platform="telegram",
        )
    except JobQueueError as exc:
        return TelegramMenuCommandResult(
            status="export_queue_failed",
            reply_text=(
                "Maaf, permintaan PDF laporan belum bisa diproses. "
                "Coba lagi beberapa saat lagi."
            ),
            reply_markup=build_main_menu(),
            error_message=exc.detail,
        )

    return TelegramMenuCommandResult(
        status="export_queued",
        transaction_status="queued",
        reply_text=(
            "Permintaan export PDF laporan bulan ini sudah masuk antrean. "
            "Bot akan mengirim file PDF setelah selesai dibuat."
        ),
        reply_markup=build_main_menu(),
        job_id=job.id,
    )


def _link_instruction_text() -> str:
    return (
        "Akun Telegram ini belum terhubung ke dashboard.\n\n"
        "Login ke dashboard, buat kode linking, lalu kirim: hubungkan KODE."
    )


def _consume_waiting_state_for_text(
    *,
    db: Session,
    user_id: int,
    text: str,
) -> str | None:
    if text.lstrip().startswith("/"):
        return None
    return consume_waiting_input_state(
        db,
        user_id=user_id,
        states={WAITING_EXPENSE_INPUT, WAITING_INCOME_INPUT},
    )


def _forced_type_from_waiting_state(waiting_state: str | None) -> str | None:
    if waiting_state == WAITING_EXPENSE_INPUT:
        return "expense"
    if waiting_state == WAITING_INCOME_INPUT:
        return "income"
    return None
