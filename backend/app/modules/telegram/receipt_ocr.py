from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import BotLog, Receipt, Transaction
from app.modules.bot.conversation_state import (
    PENDING_TRANSACTION_TTL,
    format_active_pending_message,
    get_active_pending_state,
    get_pending_transaction,
)
from app.modules.jobs.service import (
    JobQueueError,
    ReceiptOcrEnqueue,
    queue_receipt_ocr_job,
)
from app.modules.media.service import MediaStorageError, save_media_bytes
from app.modules.ocr.receipt_chat import (
    CANCEL_CONFIRMATION_RE,
    PENDING_RECEIPT_STATUSES,
    ReceiptOcrFlowResult as TelegramReceiptOcrFlowResult,
    YES_CONFIRMATION_RE,
    apply_caption_amount_if_possible,
    apply_receipt_correction,
    find_duplicate_receipt_transaction,
    find_latest_saved_receipt_transaction,
    format_duplicate_receipt_reply,
    format_receipt_confirmation,
    format_rupiah,
    receipt_category_name,
    receipt_description,
)
from app.modules.telegram.callback_handler import (
    WAITING_RECEIPT_CAPTION,
    consume_waiting_input_state_payload,
    set_waiting_input_state,
)
from app.modules.telegram.client import TelegramClient, TelegramClientError
from app.modules.telegram.client import DownloadedTelegramFile
from app.modules.telegram.parser import ParsedTelegramMessage
from app.modules.transactions.repository import find_category

CATEGORY_CREATE_MESSAGE_TYPE = "category_create"
PENDING_CATEGORY_CREATE_STATUS = "pending_category_create"


def handle_telegram_receipt_photo(
    *,
    db: Session,
    user_id: int,
    parsed: ParsedTelegramMessage,
    telegram_client: TelegramClient,
    enqueue: ReceiptOcrEnqueue,
) -> TelegramReceiptOcrFlowResult | None:
    if parsed.message_type != "photo":
        return None

    active_pending = get_active_pending_state(db, user_id=user_id)
    if active_pending is not None:
        return TelegramReceiptOcrFlowResult(
            status="active_pending",
            reply_text=format_active_pending_message(active_pending),
        )

    if not parsed.file_id:
        return TelegramReceiptOcrFlowResult(
            status="download_failed",
            reply_text=(
                "Saya menerima gambar struk, tetapi file_id dari Telegram tidak tersedia. "
                "Coba kirim ulang fotonya."
            ),
            error_message="missing_file_id",
        )

    try:
        downloaded = telegram_client.download_media(
            file_id=parsed.file_id,
            fallback_filename=parsed.file_name or "telegram-receipt.jpg",
            fallback_content_type=parsed.mime_type or "image/jpeg",
        )
        media_file = save_media_bytes(
            db,
            user_id=user_id,
            file_type="receipt",
            content=downloaded.content,
            original_filename=downloaded.filename or parsed.file_name,
            mime_type=_resolve_receipt_mime_type(parsed, downloaded),
            source="telegram_receipt",
        )
        receipt = _get_or_create_receipt(
            db,
            user_id=user_id,
            media_file_id=media_file.id,
            caption_text=parsed.text,
        )
    except (TelegramClientError, MediaStorageError) as exc:
        return TelegramReceiptOcrFlowResult(
            status="download_failed",
            reply_text=(
                "Gagal mengunduh atau menyimpan foto struk dari Telegram. "
                "Coba kirim ulang fotonya dengan gambar yang lebih jelas."
            ),
            error_message=str(exc),
        )

    try:
        job = queue_receipt_ocr_job(
            db,
            user_id=user_id,
            media_id=media_file.id,
            source="telegram",
            enqueue=enqueue,
            notify_chat_id=parsed.chat_id,
            notify_platform="telegram",
        )
    except JobQueueError as exc:
        return TelegramReceiptOcrFlowResult(
            status="limit_reached" if exc.status_code == 429 else "queue_failed",
            media_file_id=media_file.id,
            receipt_id=receipt.id,
            reply_text=_queue_error_reply(exc),
            error_message=str(exc),
        )

    if not parsed.text:
        set_waiting_input_state(
            db,
            user_id=user_id,
            chat_id=parsed.chat_id,
            state=WAITING_RECEIPT_CAPTION,
            metadata={"receipt_id": receipt.id},
        )
        db.commit()

    return TelegramReceiptOcrFlowResult(
        status="queued",
        media_file_id=media_file.id,
        receipt_id=receipt.id,
        job_id=job.id,
        reply_text=_queued_reply(has_caption=bool(parsed.text)),
    )


def handle_telegram_receipt_text(
    *,
    db: Session,
    user_id: int,
    text: str | None,
) -> TelegramReceiptOcrFlowResult | None:
    if not text or not text.strip():
        return None

    cancel_result = _handle_receipt_cancel_text(db=db, user_id=user_id, text=text)
    if cancel_result is not None:
        return cancel_result

    confirmation_result = _handle_receipt_confirmation_text(
        db=db,
        user_id=user_id,
        text=text,
    )
    if confirmation_result is not None:
        return confirmation_result

    state_payload = consume_waiting_input_state_payload(
        db,
        user_id=user_id,
        states={WAITING_RECEIPT_CAPTION},
    )
    if state_payload is None:
        return None

    receipt_id = state_payload.get("receipt_id")
    receipt = db.get(Receipt, receipt_id) if isinstance(receipt_id, int) else None
    if receipt is None or receipt.user_id != user_id or receipt.transaction_id is not None:
        db.commit()
        return TelegramReceiptOcrFlowResult(
            status="caption_receipt_not_found",
            reply_text=(
                "Keterangan diterima, tapi struk yang menunggu caption sudah tidak aktif. "
                "Kirim ulang foto struk kalau mau diproses lagi."
            ),
            error_message="receipt_not_found",
        )

    receipt.caption_text = text.strip()
    apply_caption_amount_if_possible(receipt, merchant_name="Caption Telegram")
    db.commit()
    db.refresh(receipt)

    if receipt.total_amount is not None:
        reply_text = (
            "Oke, keterangan struk sudah kusimpan.\n\n"
            f"{format_receipt_confirmation(receipt)}"
        )
    else:
        reply_text = (
            f"Oke, keterangan struk kusimpan: {receipt.caption_text}.\n"
            "Aku tetap lanjut baca OCR. Kalau total belum terbaca nanti, "
            "kamu bisa koreksi dengan format: edit total 20000."
        )

    return TelegramReceiptOcrFlowResult(
        status="caption_saved",
        receipt_id=receipt.id,
        media_file_id=receipt.media_file_id,
        reply_text=reply_text,
    )


def _get_or_create_receipt(
    db: Session,
    *,
    user_id: int,
    media_file_id: int,
    caption_text: str | None,
) -> Receipt:
    receipt = db.scalar(
        select(Receipt).where(
            Receipt.user_id == user_id,
            Receipt.media_file_id == media_file_id,
        )
    )
    if receipt is None:
        receipt = Receipt(
            user_id=user_id,
            media_file_id=media_file_id,
            caption_text=caption_text,
            status="pending",
        )
        db.add(receipt)
    elif caption_text and not receipt.caption_text:
        receipt.caption_text = caption_text
    db.commit()
    db.refresh(receipt)
    return receipt


def _resolve_receipt_mime_type(
    parsed: ParsedTelegramMessage,
    downloaded: DownloadedTelegramFile,
) -> str:
    for candidate in [parsed.mime_type, downloaded.content_type]:
        normalized = _normalize_content_type(candidate)
        if normalized and normalized != "application/octet-stream":
            return normalized

    suffix = Path(downloaded.filename or parsed.file_name or "").suffix.lower()
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".pdf":
        return "application/pdf"
    return "image/jpeg"


def _normalize_content_type(value: str | None) -> str | None:
    if not value:
        return None
    return value.split(";", 1)[0].strip().lower() or None


def _queue_error_reply(exc: JobQueueError) -> str:
    if exc.status_code == 429:
        return (
            "Batas OCR harian sudah tercapai. "
            "Coba lagi besok atau input transaksi secara manual dulu."
        )
    return (
        "Foto struk sudah diterima, tetapi job OCR gagal masuk antrean. "
        "Coba lagi beberapa saat lagi."
    )


def _queued_reply(*, has_caption: bool) -> str:
    if has_caption:
        return (
            "Foto struk diterima dan masuk antrean OCR.\n"
            "Aku lagi baca struknya. Nanti aku kirim hasil total dan tanggalnya."
        )
    return (
        "Foto struk diterima dan masuk antrean OCR.\n"
        "Aku tetap bisa baca tanpa caption.\n\n"
        "Sambil menunggu, boleh balas keterangan struknya ya. "
        "Contoh: makan siang 15 ribu atau parkir kampus 5 ribu."
    )


def _handle_receipt_confirmation_text(
    *,
    db: Session,
    user_id: int,
    text: str,
) -> TelegramReceiptOcrFlowResult | None:
    if YES_CONFIRMATION_RE.match(text):
        receipt = _find_pending_receipt(db, user_id=user_id)
        if receipt is None:
            if (
                get_pending_transaction(db, user_id=user_id) is not None
                or _has_pending_category_create(
                    db,
                    user_id=user_id,
                )
            ):
                return None
            latest_transaction = find_latest_saved_receipt_transaction(db, user_id=user_id)
            if latest_transaction is not None:
                return TelegramReceiptOcrFlowResult(
                    status="duplicate",
                    transaction_id=latest_transaction.id,
                    reply_text=format_duplicate_receipt_reply(
                        latest_transaction,
                        subject="Struk terakhir",
                    ),
                )
            return TelegramReceiptOcrFlowResult(
                status="no_pending_receipt",
                reply_text="Tidak ada struk yang sedang menunggu konfirmasi.",
            )
        return _confirm_receipt_transaction(db=db, receipt=receipt)

    receipt = _find_pending_receipt(db, user_id=user_id)
    if receipt is None:
        return None

    correction = apply_receipt_correction(receipt, text)
    if correction is None:
        return None
    if correction.error_message:
        return TelegramReceiptOcrFlowResult(
            status="edit_invalid",
            receipt_id=receipt.id,
            reply_text=correction.error_message,
            error_message="invalid_receipt_edit",
        )
    db.commit()
    db.refresh(receipt)
    return TelegramReceiptOcrFlowResult(
        status="edit_updated",
        receipt_id=receipt.id,
        reply_text=format_receipt_confirmation(receipt),
    )


def _handle_receipt_cancel_text(
    *,
    db: Session,
    user_id: int,
    text: str,
) -> TelegramReceiptOcrFlowResult | None:
    if not CANCEL_CONFIRMATION_RE.match(text):
        return None
    receipt = _find_pending_receipt(db, user_id=user_id)
    if receipt is None:
        return None
    receipt.status = "cancelled"
    db.commit()
    return TelegramReceiptOcrFlowResult(
        status="cancelled",
        receipt_id=receipt.id,
        reply_text="Oke, struk ini aku batalkan. Data kamu belum berubah.",
    )


def _confirm_receipt_transaction(
    *,
    db: Session,
    receipt: Receipt,
) -> TelegramReceiptOcrFlowResult:
    if receipt.total_amount is None:
        return TelegramReceiptOcrFlowResult(
            status="manual_input_required",
            receipt_id=receipt.id,
            reply_text=(
                "Total struk belum terbaca. Kirim koreksi dengan format: edit total 20000."
            ),
            error_message="missing_total_amount",
        )

    duplicate = find_duplicate_receipt_transaction(
        db,
        receipt,
        fallback_description="Struk Telegram",
    )
    if duplicate is not None:
        receipt.transaction_id = duplicate.id
        receipt.status = "duplicate"
        db.commit()
        return TelegramReceiptOcrFlowResult(
            status="duplicate",
            receipt_id=receipt.id,
            transaction_id=duplicate.id,
            reply_text=format_duplicate_receipt_reply(duplicate),
        )

    category = find_category(
        db=db,
        category_name=receipt_category_name(receipt),
        transaction_type="expense",
    )
    transaction = Transaction(
        user_id=receipt.user_id,
        type="expense",
        amount=receipt.total_amount,
        category_id=category.id if category else None,
        description=receipt_description(receipt, fallback="Struk Telegram"),
        transaction_date=receipt.receipt_date or date.today(),
        source="receipt_ocr",
        status="confirmed",
    )
    db.add(transaction)
    db.flush()
    receipt.transaction_id = transaction.id
    receipt.status = "confirmed"
    db.commit()
    db.refresh(transaction)
    db.refresh(receipt)

    return TelegramReceiptOcrFlowResult(
        status="saved",
        receipt_id=receipt.id,
        transaction_id=transaction.id,
        reply_text=(
            "Siap, Transaksi struk tersimpan.\n"
            f"Aku catat pengeluaran {format_rupiah(transaction.amount)}"
            + f" untuk {receipt.merchant_name or receipt.caption_text or 'Struk'} "
            f"tanggal {transaction.transaction_date.isoformat()}."
        ),
    )


def _find_pending_receipt(db: Session, *, user_id: int) -> Receipt | None:
    return db.scalar(
        select(Receipt)
        .where(
            Receipt.user_id == user_id,
            Receipt.transaction_id.is_(None),
            Receipt.status.in_(PENDING_RECEIPT_STATUSES),
        )
        .order_by(Receipt.created_at.desc(), Receipt.id.desc())
    )


def _has_pending_category_create(db: Session, *, user_id: int) -> bool:
    pending = db.scalar(
        select(BotLog)
        .where(
            BotLog.user_id == user_id,
            BotLog.message_type == CATEGORY_CREATE_MESSAGE_TYPE,
            BotLog.status == PENDING_CATEGORY_CREATE_STATUS,
        )
        .order_by(BotLog.created_at.desc(), BotLog.id.desc())
    )
    if pending is None:
        return False
    created_at = (
        pending.created_at
        if pending.created_at.tzinfo
        else pending.created_at.replace(tzinfo=timezone.utc)
    )
    if datetime.now(timezone.utc) - created_at > PENDING_TRANSACTION_TTL:
        pending.status = "expired_category_create"
        db.flush()
        return False
    return True
