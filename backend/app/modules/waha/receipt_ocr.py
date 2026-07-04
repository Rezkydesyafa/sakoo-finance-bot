from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Receipt, Transaction
from app.modules.jobs.service import (
    JobQueueError,
    ReceiptOcrEnqueue,
    queue_receipt_ocr_job,
)
from app.modules.media.service import MediaStorageError, save_media_bytes
from app.modules.ocr.receipt_chat import (
    EDIT_TOTAL_RE,
    PENDING_RECEIPT_STATUSES,
    ReceiptOcrFlowResult,
    YES_CONFIRMATION_RE,
    apply_caption_amount_if_possible,
    format_receipt_confirmation,
    format_rupiah,
    parse_total_correction,
    receipt_description,
)
from app.modules.waha.client import WahaClient, WahaClientError
from app.modules.waha.parser import ParsedWahaMessage


def handle_whatsapp_receipt_image(
    *,
    db: Session,
    user_id: int,
    parsed: ParsedWahaMessage,
    waha_client: WahaClient,
    enqueue: ReceiptOcrEnqueue,
) -> ReceiptOcrFlowResult | None:
    if parsed.message_type != "image":
        return None
    if not parsed.media_url:
        return ReceiptOcrFlowResult(
            status="download_failed",
            reply_text=(
                "Saya menerima gambar struk, tetapi URL media dari WAHA tidak tersedia. "
                "Coba kirim ulang foto struknya."
            ),
            error_message="missing_media_url",
        )

    try:
        downloaded = waha_client.download_media(parsed.media_url)
        media_file = save_media_bytes(
            db,
            user_id=user_id,
            file_type="receipt",
            content=downloaded.content,
            original_filename=downloaded.filename or parsed.media_filename,
            mime_type=parsed.media_mimetype or downloaded.content_type,
            source="whatsapp_receipt",
        )
        receipt = _store_receipt_caption(
            db,
            user_id=user_id,
            media_file_id=media_file.id,
            caption_text=parsed.text,
        )
    except (WahaClientError, MediaStorageError) as exc:
        return ReceiptOcrFlowResult(
            status="download_failed",
            reply_text=(
                "Gagal mengunduh atau menyimpan foto struk dari WhatsApp. "
                "Coba kirim ulang fotonya."
            ),
            error_message=str(exc),
        )

    try:
        job = queue_receipt_ocr_job(
            db,
            user_id=user_id,
            media_id=media_file.id,
            source="whatsapp",
            enqueue=enqueue,
            notify_chat_id=parsed.chat_id,
            notify_session=waha_client.session,
        )
    except JobQueueError as exc:
        if exc.status_code == 429:
            return ReceiptOcrFlowResult(
                status="limit_reached",
                media_file_id=media_file.id,
                receipt_id=receipt.id,
                reply_text=(
                    "Batas OCR harian kamu sudah tercapai. "
                    "Coba lagi besok agar kuota Google Vision tetap terkendali."
                ),
                error_message=str(exc),
            )
        return ReceiptOcrFlowResult(
            status="queue_failed",
            media_file_id=media_file.id,
            receipt_id=receipt.id,
            reply_text=(
                "Foto struk sudah diterima, tetapi job OCR gagal masuk antrean. "
                "Coba lagi beberapa saat lagi."
            ),
            error_message=str(exc),
        )

    return ReceiptOcrFlowResult(
        status="queued",
        media_file_id=media_file.id,
        receipt_id=receipt.id,
        job_id=job.id,
        reply_text=_queued_reply(has_caption=bool(parsed.text)),
    )


def handle_whatsapp_receipt_confirmation(
    *,
    db: Session,
    user_id: int,
    text: str | None,
) -> ReceiptOcrFlowResult | None:
    if not text:
        return None

    if YES_CONFIRMATION_RE.match(text):
        receipt = _find_pending_receipt(db, user_id=user_id)
        if receipt is None:
            return ReceiptOcrFlowResult(
                status="no_pending_receipt",
                reply_text="Tidak ada struk yang sedang menunggu konfirmasi.",
            )
        return _confirm_receipt_transaction(db=db, receipt=receipt)

    edit_requested = EDIT_TOTAL_RE.match(text) is not None
    amount = parse_total_correction(text)
    if amount is None:
        if edit_requested:
            receipt = _find_pending_receipt(db, user_id=user_id)
            return ReceiptOcrFlowResult(
                status="edit_invalid",
                receipt_id=receipt.id if receipt else None,
                reply_text="Format edit belum terbaca. Contoh: edit total 20000",
                error_message="invalid_edit_amount",
            )
        return _handle_receipt_caption_text(db=db, user_id=user_id, text=text)

    receipt = _find_pending_receipt(db, user_id=user_id)
    if receipt is None:
        return ReceiptOcrFlowResult(
            status="no_pending_receipt",
            reply_text="Tidak ada struk yang bisa diedit. Kirim foto struk terlebih dahulu.",
        )

    receipt.total_amount = amount
    receipt.confidence = Decimal("0.8000")
    receipt.status = "needs_confirmation"
    db.commit()
    db.refresh(receipt)

    return ReceiptOcrFlowResult(
        status="edit_updated",
        receipt_id=receipt.id,
        reply_text=format_receipt_confirmation(receipt),
    )


def _handle_receipt_caption_text(
    *,
    db: Session,
    user_id: int,
    text: str,
) -> ReceiptOcrFlowResult | None:
    receipt = _find_pending_receipt(db, user_id=user_id)
    if receipt is None or receipt.caption_text:
        return None

    receipt.caption_text = text.strip()
    apply_caption_amount_if_possible(receipt, merchant_name="Caption WhatsApp")
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
            "kamu bisa koreksi dengan format: 20000 atau edit total 20000."
        )

    return ReceiptOcrFlowResult(
        status="caption_saved",
        receipt_id=receipt.id,
        media_file_id=receipt.media_file_id,
        reply_text=reply_text,
    )


def _confirm_receipt_transaction(
    *,
    db: Session,
    receipt: Receipt,
) -> ReceiptOcrFlowResult:
    if receipt.total_amount is None:
        return ReceiptOcrFlowResult(
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
        description=receipt_description(receipt, fallback="Struk WhatsApp"),
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

    return ReceiptOcrFlowResult(
        status="saved",
        receipt_id=receipt.id,
        transaction_id=transaction.id,
        reply_text=(
            "Transaksi struk tersimpan: "
            f"Pengeluaran {format_rupiah(transaction.amount)} "
            f"untuk {receipt.merchant_name or 'Struk'} "
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


def _store_receipt_caption(
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
            status="pending",
        )
        db.add(receipt)
        db.flush()

    if caption_text and caption_text.strip():
        receipt.caption_text = caption_text.strip()
    return receipt


def _find_default_expense_category(db: Session) -> Category | None:
    return db.scalar(
        select(Category).where(
            func.lower(Category.name) == "lainnya",
            Category.type == "expense",
        )
    )


def _queued_reply(*, has_caption: bool) -> str:
    if has_caption:
        return (
            "Aku lagi baca struknya...\n"
            "[1/3] Foto diterima\n"
            "[2/3] masuk antrean OCR\n"
            "[3/3] Nanti aku kirim hasilnya setelah selesai diproses."
        )
    return (
        "Aku lagi baca struknya...\n"
        "[1/3] Foto diterima\n"
        "[2/3] masuk antrean OCR\n"
        "[3/3] Nanti aku kirim hasilnya setelah selesai diproses.\n\n"
        "Kalau struknya tidak punya keterangan, balas captionnya ya. "
        "Contoh: makan siang 20 ribu atau parkir kantor 5 ribu."
    )
