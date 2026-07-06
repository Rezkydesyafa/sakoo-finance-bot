from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BotLog
from app.modules.bot.response_templates import format_help_response
from app.modules.jobs.service import JobQueueError, ReportPdfEnqueue, queue_report_pdf_job
from app.modules.telegram.client import TelegramClient, TelegramClientError
from app.modules.telegram.menu import (
    ADD_EXPENSE,
    ADD_INCOME,
    ADD_RECEIPT,
    ADD_VOICE,
    BACK_HOME,
    EXPORT_MONTH,
    EXPORT_WEEK,
    HISTORY_ALL,
    HISTORY_EXPENSE,
    HISTORY_INCOME,
    HISTORY_SEARCH,
    MENU_ADD,
    MENU_BALANCE,
    MENU_EXPORT,
    MENU_HELP,
    MENU_HISTORY,
    MENU_REPORT,
    MENU_SETTINGS,
    REPORT_CATEGORY,
    REPORT_MONTH,
    REPORT_TODAY,
    REPORT_WEEK,
    SET_BUDGET,
    SET_CATEGORY,
    SET_LINK,
    build_add_menu,
    build_export_menu,
    build_history_menu,
    build_link_menu,
    build_main_menu,
    build_report_menu,
    build_settings_menu,
    callback_data_values,
)
from app.modules.telegram.parser import ParsedTelegramMessage
from app.modules.transactions.service import (
    build_balance_response,
    build_recent_transactions_response,
    build_report_summary_response,
    build_transaction_list_response,
)


WAITING_EXPENSE_INPUT = "WAITING_EXPENSE_INPUT"
WAITING_INCOME_INPUT = "WAITING_INCOME_INPUT"
WAITING_RECEIPT_CAPTION = "WAITING_RECEIPT_CAPTION"
TELEGRAM_MENU_STATE_MESSAGE_TYPE = "telegram_menu_state"
CONSUMED_MENU_STATE_STATUS = "consumed_menu_state"
SUPERSEDED_MENU_STATE_STATUS = "superseded_menu_state"
ACTIVE_WAITING_INPUT_STATES = {
    WAITING_EXPENSE_INPUT,
    WAITING_INCOME_INPUT,
    WAITING_RECEIPT_CAPTION,
}


@dataclass(frozen=True)
class TelegramCallbackResult:
    status: str
    callback_data: str | None
    reply_status: str | None
    transaction_status: str | None = None
    job_id: int | None = None
    error_message: str | None = None

    def to_log_payload(self) -> dict[str, Any]:
        return asdict(self)


def handle_callback_query(
    *,
    db: Session,
    parsed: ParsedTelegramMessage,
    linked_user_id: int | None,
    telegram_client: TelegramClient,
    enqueue: ReportPdfEnqueue,
) -> TelegramCallbackResult:
    data = parsed.callback_data
    if data not in callback_data_values():
        return _respond_to_callback(
            parsed=parsed,
            telegram_client=telegram_client,
            text="Menu tidak dikenal. Coba buka /start lagi.",
            reply_markup=build_main_menu(),
            status="unknown_callback",
            answer_text="Menu tidak dikenal",
            show_alert=True,
        )

    if data == BACK_HOME:
        return _respond_to_callback(
            parsed=parsed,
            telegram_client=telegram_client,
            text=build_welcome_text(),
            reply_markup=build_main_menu(),
            status="main_menu",
        )
    if data == MENU_ADD:
        return _respond_to_callback(
            parsed=parsed,
            telegram_client=telegram_client,
            text="Mau catat transaksi dari mana?",
            reply_markup=build_add_menu(),
            status="add_menu",
        )
    if data == MENU_REPORT:
        return _respond_to_callback(
            parsed=parsed,
            telegram_client=telegram_client,
            text="Pilih periode laporan yang mau kamu lihat.",
            reply_markup=build_report_menu(),
            status="report_menu",
        )
    if data == MENU_EXPORT:
        return _respond_to_callback(
            parsed=parsed,
            telegram_client=telegram_client,
            text="Pilih laporan PDF yang mau dibuat.",
            reply_markup=build_export_menu(),
            status="export_menu",
        )
    if data == MENU_HISTORY:
        return _respond_to_callback(
            parsed=parsed,
            telegram_client=telegram_client,
            text="Pilih riwayat transaksi yang mau dicek.",
            reply_markup=build_history_menu(),
            status="history_menu",
        )
    if data == MENU_SETTINGS:
        return _respond_to_callback(
            parsed=parsed,
            telegram_client=telegram_client,
            text="Pengaturan akun Sakoo.",
            reply_markup=build_settings_menu(),
            status="settings_menu",
        )
    if data == MENU_HELP:
        return _respond_to_callback(
            parsed=parsed,
            telegram_client=telegram_client,
            text=format_help_response(),
            reply_markup=build_main_menu(),
            status="help",
        )

    if linked_user_id is None:
        return _respond_to_callback(
            parsed=parsed,
            telegram_client=telegram_client,
            text=_link_instruction_text(),
            reply_markup=build_link_menu(),
            status="unlinked",
            answer_text="Hubungkan akun dulu",
            show_alert=True,
        )

    if data == MENU_BALANCE:
        return _respond_to_callback(
            parsed=parsed,
            telegram_client=telegram_client,
            text=build_balance_response(db, linked_user_id),
            reply_markup=build_main_menu(),
            status="balance",
            transaction_status="balance",
        )
    if data == ADD_EXPENSE:
        set_waiting_input_state(
            db,
            user_id=linked_user_id,
            chat_id=parsed.chat_id,
            state=WAITING_EXPENSE_INPUT,
        )
        return _respond_to_callback(
            parsed=parsed,
            telegram_client=telegram_client,
            text=(
                "Mode catat pengeluaran aktif.\n\n"
                "Kirim detail pengeluaran berikutnya, contoh: beli makan 20 ribu."
            ),
            reply_markup=build_main_menu(),
            status=WAITING_EXPENSE_INPUT,
            answer_text="Kirim detail pengeluaran",
        )
    if data == ADD_INCOME:
        set_waiting_input_state(
            db,
            user_id=linked_user_id,
            chat_id=parsed.chat_id,
            state=WAITING_INCOME_INPUT,
        )
        return _respond_to_callback(
            parsed=parsed,
            telegram_client=telegram_client,
            text=(
                "Mode catat pemasukan aktif.\n\n"
                "Kirim detail pemasukan berikutnya, contoh: uang jajan 200 ribu."
            ),
            reply_markup=build_main_menu(),
            status=WAITING_INCOME_INPUT,
            answer_text="Kirim detail pemasukan",
        )
    if data == ADD_RECEIPT:
        return _respond_to_callback(
            parsed=parsed,
            telegram_client=telegram_client,
            text=(
                "Upload foto struk dari Telegram, lalu tambahkan caption kalau perlu. "
                "Kalau OCR kurang jelas, caption akan dipakai sebagai fallback."
            ),
            reply_markup=build_add_menu(),
            status="receipt_instruction",
        )
    if data == ADD_VOICE:
        return _respond_to_callback(
            parsed=parsed,
            telegram_client=telegram_client,
            text="Kirim voice note berisi transaksi, maksimal 30 detik.",
            reply_markup=build_add_menu(),
            status="voice_instruction",
        )

    if data in {REPORT_TODAY, REPORT_WEEK, REPORT_MONTH, REPORT_CATEGORY}:
        period = {
            REPORT_TODAY: "day",
            REPORT_WEEK: "week",
            REPORT_MONTH: "month",
            REPORT_CATEGORY: "month",
        }[data]
        return _respond_to_callback(
            parsed=parsed,
            telegram_client=telegram_client,
            text=build_report_summary_response(db, linked_user_id, period),
            reply_markup=build_report_menu(),
            status=f"report_{period}",
            transaction_status="report",
        )

    if data in {EXPORT_WEEK, EXPORT_MONTH}:
        return _handle_export_callback(
            db=db,
            parsed=parsed,
            linked_user_id=linked_user_id,
            telegram_client=telegram_client,
            enqueue=enqueue,
            period="week" if data == EXPORT_WEEK else "month",
        )

    if data == HISTORY_ALL:
        text = build_recent_transactions_response(db, linked_user_id)
    elif data == HISTORY_EXPENSE:
        text = build_transaction_list_response(
            db,
            linked_user_id,
            transaction_type="expense",
            period=None,
        )
    elif data == HISTORY_INCOME:
        text = build_transaction_list_response(
            db,
            linked_user_id,
            transaction_type="income",
            period=None,
        )
    elif data == HISTORY_SEARCH:
        text = "Fitur cari transaksi: ketik kata kunci, contoh cari kopi atau cari gojek."
    elif data == SET_LINK:
        text = _link_instruction_text()
    elif data == SET_CATEGORY:
        text = "Pengaturan kategori dari Telegram belum aktif. Untuk sekarang, atur dari dashboard."
    elif data == SET_BUDGET:
        text = "Pengaturan budget dari Telegram belum aktif. Untuk sekarang, atur dari dashboard."
    else:
        text = "Menu belum tersedia."

    if data == SET_LINK:
        reply_markup = build_link_menu()
    else:
        reply_markup = build_history_menu() if data.startswith("HISTORY_") else build_settings_menu()
    return _respond_to_callback(
        parsed=parsed,
        telegram_client=telegram_client,
        text=text,
        reply_markup=reply_markup,
        status=data.lower(),
    )


def build_welcome_text() -> str:
    return (
        "Halo, ini Sakoo Finance Bot.\n\n"
        "Pakai tombol di bawah untuk cek saldo, catat transaksi, lihat laporan, "
        "atau export PDF. Kamu juga tetap bisa kirim natural seperti: beli makan 20 ribu."
    )


def set_waiting_input_state(
    db: Session,
    *,
    user_id: int,
    chat_id: str | None,
    state: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    if state not in ACTIVE_WAITING_INPUT_STATES:
        return

    for existing in _get_waiting_state_logs(db, user_id=user_id):
        existing.status = SUPERSEDED_MENU_STATE_STATUS

    payload = {"state": state, "chat_id": chat_id}
    if metadata:
        payload.update(metadata)

    db.add(
        BotLog(
            user_id=user_id,
            platform="telegram",
            message_type=TELEGRAM_MENU_STATE_MESSAGE_TYPE,
            raw_message=chat_id,
            parsed_result=payload,
            status=state,
        )
    )
    db.flush()


def consume_waiting_input_state(
    db: Session,
    *,
    user_id: int,
    states: set[str] | None = None,
) -> str | None:
    payload = consume_waiting_input_state_payload(
        db,
        user_id=user_id,
        states=states,
    )
    if payload is None:
        return None
    state = payload.get("state")
    return state if isinstance(state, str) else None


def consume_waiting_input_state_payload(
    db: Session,
    *,
    user_id: int,
    states: set[str] | None = None,
) -> dict[str, Any] | None:
    allowed_states = states or ACTIVE_WAITING_INPUT_STATES
    state_log = db.scalar(
        select(BotLog)
        .where(
            BotLog.user_id == user_id,
            BotLog.platform == "telegram",
            BotLog.message_type == TELEGRAM_MENU_STATE_MESSAGE_TYPE,
            BotLog.status.in_(allowed_states),
        )
        .order_by(BotLog.created_at.desc(), BotLog.id.desc())
    )
    if state_log is None:
        return None

    payload = state_log.parsed_result or {}
    state = payload.get("state") if isinstance(payload, dict) else state_log.status
    state_log.status = CONSUMED_MENU_STATE_STATUS
    db.flush()
    if state not in allowed_states:
        return None
    return payload if isinstance(payload, dict) else {"state": state}


def _get_waiting_state_logs(db: Session, *, user_id: int) -> list[BotLog]:
    return list(
        db.scalars(
            select(BotLog).where(
                BotLog.user_id == user_id,
                BotLog.platform == "telegram",
                BotLog.message_type == TELEGRAM_MENU_STATE_MESSAGE_TYPE,
                BotLog.status.in_(ACTIVE_WAITING_INPUT_STATES),
            )
        )
    )


def _handle_export_callback(
    *,
    db: Session,
    parsed: ParsedTelegramMessage,
    linked_user_id: int,
    telegram_client: TelegramClient,
    enqueue: ReportPdfEnqueue,
    period: str,
) -> TelegramCallbackResult:
    try:
        job = queue_report_pdf_job(
            db,
            user_id=linked_user_id,
            period=period,
            anchor_date=date.today(),
            source="telegram_bot",
            enqueue=enqueue,
            notify_chat_id=parsed.chat_id,
            notify_platform="telegram",
        )
    except JobQueueError as exc:
        return _respond_to_callback(
            parsed=parsed,
            telegram_client=telegram_client,
            text=(
                "Maaf, permintaan PDF laporan belum bisa diproses. "
                "Coba lagi beberapa saat lagi."
            ),
            reply_markup=build_export_menu(),
            status="export_queue_failed",
            error_message=exc.detail,
        )

    label = "minggu ini" if period == "week" else "bulan ini"
    return _respond_to_callback(
        parsed=parsed,
        telegram_client=telegram_client,
        text=(
            f"Siap, aku buatin export PDF laporan {label}. "
            f"Permintaan export PDF laporan {label} sudah masuk antrean, "
            "nanti aku kirim file PDF-nya setelah selesai."
        ),
        reply_markup=build_export_menu(),
        status="export_queued",
        transaction_status="queued",
        job_id=job.id,
    )


def _respond_to_callback(
    *,
    parsed: ParsedTelegramMessage,
    telegram_client: TelegramClient,
    text: str,
    reply_markup: dict[str, Any] | None,
    status: str,
    answer_text: str | None = None,
    show_alert: bool = False,
    transaction_status: str | None = None,
    job_id: int | None = None,
    error_message: str | None = None,
) -> TelegramCallbackResult:
    reply_status = "sent"
    callback_error = error_message

    try:
        if parsed.callback_query_id:
            telegram_client.answer_callback_query(
                callback_query_id=parsed.callback_query_id,
                text=answer_text,
                show_alert=show_alert,
            )

        if parsed.chat_id and parsed.message_id:
            telegram_client.edit_message_text(
                chat_id=parsed.chat_id,
                message_id=parsed.message_id,
                text=text,
                reply_markup=reply_markup,
            )
        elif parsed.chat_id:
            telegram_client.send_message(
                chat_id=parsed.chat_id,
                text=text,
                reply_markup=reply_markup,
            )
        else:
            reply_status = "failed"
            callback_error = _append_error(callback_error, "missing_chat_id")
    except TelegramClientError as exc:
        reply_status = "failed"
        callback_error = _append_error(callback_error, str(exc))

    return TelegramCallbackResult(
        status=status,
        callback_data=parsed.callback_data,
        reply_status=reply_status,
        transaction_status=transaction_status,
        job_id=job_id,
        error_message=callback_error,
    )


def _link_instruction_text() -> str:
    return (
        "Silakan daftar atau login di dashboard Sakoo untuk memulai bot.\n\n"
        "Setelah masuk, buka Connected Bots, buat kode linking, lalu kirim ke bot:\n"
        "hubungkan KODE"
    )


def _append_error(existing: str | None, new_error: str) -> str:
    return f"{existing}; {new_error}" if existing else new_error
