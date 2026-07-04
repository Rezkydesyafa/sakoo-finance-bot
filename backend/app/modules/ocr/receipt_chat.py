import re
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Receipt, Transaction
from app.modules.parser.transaction_text import parse_transaction_text


YES_CONFIRMATION_RE = re.compile(
    r"^\s*(?:ya|iya|y|yes|ok|oke|benar|setuju|simpan)\s*$",
    re.IGNORECASE,
)
EDIT_TOTAL_RE = re.compile(r"^\s*edit(?:\s+total)?\s+(?P<amount>.+?)\s*$", re.IGNORECASE)
AMOUNT_ONLY_RE = re.compile(r"^\s*(?P<amount>(?:rp\s*)?\d[\d.,\s]*(?:ribu|rb|k)?)\s*$", re.IGNORECASE)
PENDING_RECEIPT_STATUSES = (
    "pending",
    "processed",
    "needs_confirmation",
    "manual_input_required",
)


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


def parse_total_correction(text: str) -> Decimal | None:
    edit_match = EDIT_TOTAL_RE.match(text)
    amount_text = edit_match.group("amount") if edit_match else None
    if amount_text is None:
        amount_match = AMOUNT_ONLY_RE.match(text)
        amount_text = amount_match.group("amount") if amount_match else None
    return _parse_edit_amount(amount_text) if amount_text else None


def apply_caption_amount_if_possible(receipt: Receipt, *, merchant_name: str) -> None:
    if not receipt.caption_text:
        return
    parsed_caption = parse_transaction_text(receipt.caption_text)
    if parsed_caption.intent != "add_transaction" or parsed_caption.amount is None:
        return
    receipt.total_amount = receipt.total_amount or parsed_caption.amount
    receipt.receipt_date = receipt.receipt_date or parsed_caption.transaction_date
    receipt.merchant_name = receipt.merchant_name or merchant_name
    receipt.confidence = max(receipt.confidence or 0, Decimal("0.7000"))
    receipt.status = "needs_confirmation"


def receipt_description(receipt: Receipt, *, fallback: str) -> str:
    if receipt.caption_text:
        parsed_caption = parse_transaction_text(receipt.caption_text)
        if parsed_caption.description:
            return parsed_caption.description
    if receipt.merchant_name:
        return f"Struk {receipt.merchant_name}"
    return fallback


def find_duplicate_receipt_transaction(
    db: Session,
    receipt: Receipt,
    *,
    fallback_description: str,
) -> Transaction | None:
    if receipt.transaction_id:
        return db.get(Transaction, receipt.transaction_id)
    if receipt.total_amount is None:
        return None

    transaction_date = receipt.receipt_date or date.today()
    description = receipt_description(receipt, fallback=fallback_description)
    return db.scalar(
        select(Transaction)
        .where(
            Transaction.user_id == receipt.user_id,
            Transaction.source == "receipt_ocr",
            Transaction.type == "expense",
            Transaction.amount == receipt.total_amount,
            Transaction.transaction_date == transaction_date,
            Transaction.description == description,
        )
        .order_by(Transaction.id.desc())
    )


def find_latest_saved_receipt_transaction(
    db: Session,
    *,
    user_id: int,
) -> Transaction | None:
    return db.scalar(
        select(Transaction)
        .join(Receipt, Receipt.transaction_id == Transaction.id)
        .where(
            Receipt.user_id == user_id,
            Receipt.transaction_id.is_not(None),
            Receipt.status.in_(("confirmed", "duplicate")),
        )
        .order_by(Receipt.created_at.desc(), Receipt.id.desc())
    )


def format_duplicate_receipt_reply(
    transaction: Transaction,
    *,
    subject: str = "Struk ini",
) -> str:
    return (
        f"{subject} sudah pernah disimpan sebagai transaksi "
        f"{format_rupiah(transaction.amount)} pada {transaction.transaction_date.isoformat()}. "
        "Aku tidak simpan lagi supaya tidak dobel."
    )


def format_receipt_confirmation(receipt: Receipt) -> str:
    merchant = receipt.merchant_name or "merchant belum terbaca"
    receipt_date = receipt.receipt_date.isoformat() if receipt.receipt_date else "tanggal belum terbaca"
    confidence = f"{float(receipt.confidence or Decimal('0')) * 100:.0f}%"
    date_note = (
        " Tanggal tidak jelas, aku pakai tanggal hari ini kalau kamu simpan."
        if receipt.receipt_date is None
        else ""
    )

    if receipt.total_amount is None:
        fallback_text = (
            " Foto agak blur atau nominal tidak terlihat. Coba foto ulang dari atas, "
            "atau kirim caption: beli makan 20 ribu."
            if not receipt.caption_text
            else " Caption yang kamu kirim belum punya nominal yang jelas."
        )
        return (
            "Total belum terbaca dari struk. "
            f"Merchant: {merchant}. Tanggal: {receipt_date}. "
            "Kirim nominalnya, contoh: 20000 atau edit total 20000."
            f"{date_note}"
            f"{fallback_text}"
        )

    used_caption_fallback = (
        bool(receipt.caption_text)
        and receipt.status == "needs_confirmation"
        and (receipt.confidence or Decimal("0")) == Decimal("0.7000")
    )
    fallback_note = " Total ini aku ambil dari caption karena OCR belum cukup jelas. " if used_caption_fallback else ""
    return (
        "Foto struk sudah diproses OCR. "
        f"Merchant: {merchant}. Tanggal: {receipt_date}. "
        f"Total: {format_rupiah(receipt.total_amount)}. "
        f"Confidence: {confidence}. "
        f"{fallback_note}"
        f"{date_note}"
        "Balas YA untuk simpan, atau kirim koreksi seperti: 20000 / edit total 20000."
    )


def format_rupiah(value: Decimal | None) -> str:
    if value is None:
        return "Rp0"
    return f"Rp{int(value):,}".replace(",", ".")


def _parse_edit_amount(value: str) -> Decimal | None:
    parsed = parse_transaction_text(f"beli struk {value}")
    return parsed.amount
