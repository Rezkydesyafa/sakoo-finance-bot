from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Receipt, Transaction
from app.modules.jobs.service import (
    JobQueueError,
    ReceiptOcrEnqueue,
    queue_receipt_ocr_job,
)
from app.modules.media.service import MediaStorageError, save_media_bytes
from app.modules.parser.transaction_text import parse_transaction_text
from app.modules.telegram.callback_handler import (
    WAITING_RECEIPT_CAPTION,
    consume_waiting_input_state_payload,
    set_waiting_input_state,
)
from app.modules.telegram.client import TelegramClient, TelegramClientError
from app.modules.telegram.client import DownloadedTelegramFile
from app.modules.telegram.parser import ParsedTelegramMessage
from app.modules.waha.receipt_ocr import (
    EDIT_TOTAL_RE,
    PENDING_RECEIPT_STATUSES,
    YES_CONFIRMATION_RE,
    format_receipt_confirmation,
)


@dataclass(frozen=True)
class TelegramReceiptOcrFlowResult:
    status: str
    reply_text: str | None = None
    media_file_id: int | None = None
    receipt_id: int | None = None
    job_id: int | None = None
    error_message: str | None = None

    def to_log_payload(self) -> dict[str, object]:
        return asdict(self)


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
    _apply_caption_amount_if_possible(receipt)
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
            return None
        return _confirm_receipt_transaction(db=db, receipt=receipt)

    edit_match = EDIT_TOTAL_RE.match(text)
    if not edit_match:
        return None

    receipt = _find_pending_receipt(db, user_id=user_id)
    if receipt is None:
        return TelegramReceiptOcrFlowResult(
            status="no_pending_receipt",
            reply_text="Tidak ada struk yang bisa diedit. Kirim foto struk terlebih dahulu.",
        )

    amount = parse_transaction_text(f"beli struk {edit_match.group('amount')}").amount
    if amount is None:
        return TelegramReceiptOcrFlowResult(
            status="edit_invalid",
            receipt_id=receipt.id,
            reply_text="Format edit belum terbaca. Contoh: edit total 20000",
            error_message="invalid_edit_amount",
        )

    receipt.total_amount = amount
    receipt.confidence = Decimal("0.8000")
    receipt.status = "needs_confirmation"
    db.commit()
    db.refresh(receipt)
    return TelegramReceiptOcrFlowResult(
        status="edit_updated",
        receipt_id=receipt.id,
        reply_text=format_receipt_confirmation(receipt),
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

    category = _find_default_expense_category(db)
    transaction = Transaction(
        user_id=receipt.user_id,
        type="expense",
        amount=receipt.total_amount,
        category_id=category.id if category else None,
        description=_receipt_description(receipt),
        transaction_date=receipt.receipt_date or date.today(),
        source="receipt_ocr",
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
            "Transaksi struk tersimpan: "
            f"Pengeluaran Rp{int(transaction.amount):,}".replace(",", ".")
            + f" untuk {receipt.merchant_name or receipt.caption_text or 'Struk'} "
            f"pada {transaction.transaction_date.isoformat()}."
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


def _find_default_expense_category(db: Session) -> Category | None:
    return db.scalar(
        select(Category).where(
            func.lower(Category.name) == "lainnya",
            Category.type == "expense",
        )
    )


def _receipt_description(receipt: Receipt) -> str:
    if receipt.caption_text:
        parsed_caption = parse_transaction_text(receipt.caption_text)
        if parsed_caption.description:
            return parsed_caption.description
    if receipt.merchant_name:
        return f"Struk {receipt.merchant_name}"
    return "Struk Telegram"


def _apply_caption_amount_if_possible(receipt: Receipt) -> None:
    if not receipt.caption_text:
        return
    parsed_caption = parse_transaction_text(receipt.caption_text)
    if parsed_caption.intent != "add_transaction" or parsed_caption.amount is None:
        return
    receipt.total_amount = receipt.total_amount or parsed_caption.amount
    receipt.receipt_date = receipt.receipt_date or parsed_caption.transaction_date
    receipt.merchant_name = receipt.merchant_name or "Caption Telegram"
    receipt.confidence = max(receipt.confidence or 0, Decimal("0.7000"))
    receipt.status = "needs_confirmation"
