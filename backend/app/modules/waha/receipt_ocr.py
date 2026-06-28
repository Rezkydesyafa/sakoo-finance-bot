import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Job, Receipt, Transaction
from app.modules.media.service import MediaStorageError, save_media_bytes
from app.modules.ocr.client import OcrClient, OcrClientError
from app.modules.ocr.service import ReceiptOcrError, process_receipt_ocr
from app.modules.parser.transaction_text import parse_transaction_text
from app.modules.waha.client import WahaClient, WahaClientError
from app.modules.waha.parser import ParsedWahaMessage


YES_CONFIRMATION_RE = re.compile(
    r"^\s*(?:ya|iya|y|yes|ok|oke|benar|setuju|simpan)\s*$",
    re.IGNORECASE,
)
EDIT_TOTAL_RE = re.compile(r"^\s*edit(?:\s+total)?\s+(?P<amount>.+?)\s*$", re.IGNORECASE)
PENDING_RECEIPT_STATUSES = ("processed", "needs_confirmation", "manual_input_required")


@dataclass(frozen=True)
class ReceiptOcrFlowResult:
    status: str
    reply_text: str | None = None
    media_file_id: int | None = None
    receipt_id: int | None = None
    job_id: int | None = None
    transaction_id: int | None = None
    error_message: str | None = None

    def to_log_payload(self) -> dict[str, Any]:
        return asdict(self)


def handle_whatsapp_receipt_image(
    *,
    db: Session,
    user_id: int,
    parsed: ParsedWahaMessage,
    waha_client: WahaClient,
    ocr_client: OcrClient,
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
    except (WahaClientError, MediaStorageError) as exc:
        return ReceiptOcrFlowResult(
            status="download_failed",
            reply_text=(
                "Gagal mengunduh atau menyimpan foto struk dari WhatsApp. "
                "Coba kirim ulang fotonya."
            ),
            error_message=str(exc),
        )

    job = Job(user_id=user_id, job_type="receipt_ocr", status="pending")
    db.add(job)
    db.flush()

    try:
        receipt = process_receipt_ocr(
            db,
            user_id=user_id,
            media_id=media_file.id,
            ocr_client=ocr_client,
        )
    except (ReceiptOcrError, OcrClientError) as exc:
        _mark_job_failed(db, job, str(exc))
        return ReceiptOcrFlowResult(
            status="ocr_failed",
            media_file_id=media_file.id,
            job_id=job.id,
            reply_text=(
                "Foto struk sudah diterima, tetapi OCR gagal diproses. "
                "Coba kirim ulang foto yang lebih jelas."
            ),
            error_message=str(exc),
        )

    job.status = "completed"
    job.result_id = receipt.id
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(job)
    db.refresh(receipt)

    return ReceiptOcrFlowResult(
        status=receipt.status,
        media_file_id=media_file.id,
        receipt_id=receipt.id,
        job_id=job.id,
        reply_text=_format_receipt_confirmation(receipt),
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

    edit_match = EDIT_TOTAL_RE.match(text)
    if not edit_match:
        return None

    receipt = _find_pending_receipt(db, user_id=user_id)
    if receipt is None:
        return ReceiptOcrFlowResult(
            status="no_pending_receipt",
            reply_text="Tidak ada struk yang bisa diedit. Kirim foto struk terlebih dahulu.",
        )

    amount = _parse_edit_amount(edit_match.group("amount"))
    if amount is None:
        return ReceiptOcrFlowResult(
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

    return ReceiptOcrFlowResult(
        status="edit_updated",
        receipt_id=receipt.id,
        reply_text=_format_receipt_confirmation(receipt),
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

    return ReceiptOcrFlowResult(
        status="saved",
        receipt_id=receipt.id,
        transaction_id=transaction.id,
        reply_text=(
            "Transaksi struk tersimpan: "
            f"Pengeluaran {_format_rupiah(transaction.amount)} "
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


def _find_default_expense_category(db: Session) -> Category | None:
    return db.scalar(
        select(Category).where(
            func.lower(Category.name) == "lainnya",
            Category.type == "expense",
        )
    )


def _parse_edit_amount(value: str) -> Decimal | None:
    parsed = parse_transaction_text(f"beli struk {value}")
    return parsed.amount


def _receipt_description(receipt: Receipt) -> str:
    if receipt.merchant_name:
        return f"Struk {receipt.merchant_name}"
    return "Struk WhatsApp"


def _format_receipt_confirmation(receipt: Receipt) -> str:
    merchant = receipt.merchant_name or "merchant belum terbaca"
    receipt_date = receipt.receipt_date.isoformat() if receipt.receipt_date else "tanggal belum terbaca"
    confidence = f"{float(receipt.confidence or Decimal('0')) * 100:.0f}%"

    if receipt.total_amount is None:
        return (
            "Foto struk sudah diproses OCR, tetapi total belanja belum terbaca. "
            f"Merchant: {merchant}. Tanggal: {receipt_date}. "
            "Kirim koreksi dengan format: edit total 20000."
        )

    return (
        "Foto struk sudah diproses OCR. "
        f"Merchant: {merchant}. Tanggal: {receipt_date}. "
        f"Total: {_format_rupiah(receipt.total_amount)}. "
        f"Confidence: {confidence}. "
        "Ketik YA untuk menyimpan transaksi, atau edit total 20000 untuk koreksi."
    )


def _format_rupiah(value: Decimal | None) -> str:
    if value is None:
        return "Rp0"
    return f"Rp{int(value):,}".replace(",", ".")


def _mark_job_failed(db: Session, job: Job, error_message: str) -> None:
    job.status = "failed"
    job.error_message = error_message
    job.completed_at = datetime.now(timezone.utc)
    db.commit()
