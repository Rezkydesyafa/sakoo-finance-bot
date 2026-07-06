import re
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Receipt, Transaction
from app.modules.ocr.receipt_parser import extract_receipt_item_names
from app.modules.parser.date_parser import parse_transaction_date
from app.modules.parser.transaction_text import parse_transaction_text


YES_CONFIRMATION_RE = re.compile(
    r"^\s*(?:ya|iya|y|yes|ok|oke|benar|setuju|simpan)\s*$",
    re.IGNORECASE,
)
EDIT_TOTAL_RE = re.compile(r"^\s*edit(?:\s+total)?\s+(?P<amount>.+?)\s*$", re.IGNORECASE)
EDIT_DATE_RE = re.compile(r"^\s*edit\s+tanggal\s+(?P<date>.+?)\s*$", re.IGNORECASE)
EDIT_MERCHANT_RE = re.compile(r"^\s*edit\s+merchant\s+(?P<merchant>.+?)\s*$", re.IGNORECASE)
EDIT_CATEGORY_RE = re.compile(r"^\s*edit\s+kategori\s+(?P<category>.+?)\s*$", re.IGNORECASE)
EDIT_NOTE_RE = re.compile(r"^\s*edit\s+(?:catatan|note)\s+(?P<note>.+?)\s*$", re.IGNORECASE)
EDIT_FREE_NOTE_RE = re.compile(
    r"^\s*edit\s+(?!(?:total|tanggal|merchant|kategori|catatan|note)\b)(?P<note>.+?)\s*$",
    re.IGNORECASE,
)
EDIT_PREFIX_RE = re.compile(r"^\s*edit\b", re.IGNORECASE)
AMOUNT_ONLY_RE = re.compile(r"^\s*(?P<amount>(?:rp\s*)?\d[\d.,\s]*(?:ribu|rb|k)?)\s*$", re.IGNORECASE)
CATEGORY_MARKER_RE = re.compile(r"\s*\[kategori:(?P<category>[^\]]+)\]\s*", re.IGNORECASE)
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


@dataclass(frozen=True)
class ReceiptCorrectionResult:
    error_message: str | None = None


def parse_total_correction(text: str) -> Decimal | None:
    edit_match = EDIT_TOTAL_RE.match(text)
    amount_text = edit_match.group("amount") if edit_match else None
    if amount_text is None:
        amount_match = AMOUNT_ONLY_RE.match(text)
        amount_text = amount_match.group("amount") if amount_match else None
    return _parse_edit_amount(amount_text) if amount_text else None


def apply_caption_amount_if_possible(receipt: Receipt, *, merchant_name: str) -> None:
    caption_text = receipt_caption_note(receipt)
    if not caption_text:
        return
    parsed_caption = parse_transaction_text(caption_text)
    if parsed_caption.intent != "add_transaction" or parsed_caption.amount is None:
        return
    receipt.total_amount = receipt.total_amount or parsed_caption.amount
    receipt.receipt_date = receipt.receipt_date or parsed_caption.transaction_date
    receipt.merchant_name = receipt.merchant_name or merchant_name
    receipt.confidence = max(receipt.confidence or 0, Decimal("0.7000"))
    receipt.status = "needs_confirmation"


def receipt_description(receipt: Receipt, *, fallback: str) -> str:
    caption_text = receipt_caption_note(receipt)
    if caption_text:
        parsed_caption = parse_transaction_text(caption_text)
        if parsed_caption.description:
            return parsed_caption.description
        return caption_text
    if receipt.ocr_text:
        item_names = extract_receipt_item_names(receipt.ocr_text, limit=3)
        if item_names:
            return ", ".join(item_names)
    if receipt.merchant_name:
        return f"Struk {receipt.merchant_name}"
    return fallback


def receipt_category_name(receipt: Receipt) -> str | None:
    marker = _category_marker(receipt.caption_text)
    if marker:
        return marker
    caption_text = receipt_caption_note(receipt)
    if not caption_text:
        return None
    parsed_caption = parse_transaction_text(caption_text)
    return parsed_caption.category


def receipt_caption_note(receipt: Receipt) -> str | None:
    if not receipt.caption_text:
        return None
    text = CATEGORY_MARKER_RE.sub(" ", receipt.caption_text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def apply_receipt_correction(receipt: Receipt, text: str) -> ReceiptCorrectionResult | None:
    text = _normalize_receipt_edit_text(text)
    amount = parse_total_correction(text)
    if amount is not None:
        receipt.total_amount = amount
        receipt.confidence = Decimal("0.8000")
        receipt.status = "needs_confirmation"
        return ReceiptCorrectionResult()

    if match := EDIT_DATE_RE.match(text):
        parsed_date = parse_transaction_date(match.group("date"), date.today())
        if parsed_date is None:
            return ReceiptCorrectionResult("Tanggal belum terbaca. Contoh: edit tanggal kemarin")
        receipt.receipt_date = parsed_date.value
        receipt.status = "needs_confirmation"
        return ReceiptCorrectionResult()

    if match := EDIT_MERCHANT_RE.match(text):
        receipt.merchant_name = _clean_edit_value(match.group("merchant"))
        receipt.status = "needs_confirmation"
        return ReceiptCorrectionResult()

    if match := EDIT_CATEGORY_RE.match(text):
        _set_receipt_category(receipt, _category_name_from_alias(match.group("category")))
        receipt.status = "needs_confirmation"
        return ReceiptCorrectionResult()

    if match := EDIT_NOTE_RE.match(text):
        _set_receipt_note(receipt, _clean_edit_value(match.group("note")))
        receipt.status = "needs_confirmation"
        return ReceiptCorrectionResult()

    if match := EDIT_FREE_NOTE_RE.match(text):
        _set_receipt_note(receipt, _clean_edit_value(match.group("note")))
        receipt.status = "needs_confirmation"
        return ReceiptCorrectionResult()

    if EDIT_PREFIX_RE.match(text):
        return ReceiptCorrectionResult(
            "Format edit belum terbaca. Contoh: edit total 20000, edit tanggal kemarin, "
            "edit kategori makan, edit catatan sarapan."
        )
    return None


def _normalize_receipt_edit_text(text: str) -> str:
    return re.sub(r"^\s*/(?=edit\b)", "", text.strip(), flags=re.IGNORECASE)


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
            Transaction.status == "confirmed",
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
            Transaction.status == "confirmed",
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
    category = receipt_category_name(receipt)
    note = receipt_caption_note(receipt)
    item_names = extract_receipt_item_names(receipt.ocr_text or "", limit=3)
    detail_lines = [
        f"Tanggal: {receipt_date}",
        f"Kategori: {category or 'belum dipilih'}",
    ]
    if receipt.merchant_name:
        detail_lines.insert(0, f"Merchant: {merchant}")
    if note:
        detail_lines.append(f"Catatan: {note}")
    elif item_names:
        detail_lines.append(f"Item: {', '.join(item_names)}")
    if receipt.receipt_date is None:
        detail_lines.append("Tanggal belum jelas, aku pakai hari ini kalau kamu simpan.")

    if receipt.total_amount is None:
        return (
            "Hasil OCR belum lengkap.\n\n"
            + "\n".join(detail_lines)
            + "\nNominal: belum terbaca\n\n"
            "Kirim nominalnya, contoh: edit total 50000."
        )

    used_caption_fallback = (
        bool(receipt.caption_text)
        and receipt.status == "needs_confirmation"
        and (receipt.confidence or Decimal("0")) == Decimal("0.7000")
    )
    if used_caption_fallback:
        detail_lines.append("Nominal diambil dari caption karena OCR belum cukup jelas.")
    return (
        "Hasil OCR:\n\n"
        + "\n".join(detail_lines)
        + f"\nTotal: {format_rupiah(receipt.total_amount)}"
        + f"\nConfidence: {confidence}\n\n"
        "Balas YA untuk simpan, atau koreksi: edit total 20000 / edit tanggal kemarin / "
        "edit kategori makan / edit catatan sarapan."
    )


def format_rupiah(value: Decimal | None) -> str:
    if value is None:
        return "Rp0"
    return f"Rp{int(value):,}".replace(",", ".")


def _parse_edit_amount(value: str) -> Decimal | None:
    parsed = parse_transaction_text(f"beli struk {value}")
    return parsed.amount


def _category_marker(value: str | None) -> str | None:
    if not value:
        return None
    match = CATEGORY_MARKER_RE.search(value)
    return match.group("category").strip() if match else None


def _set_receipt_note(receipt: Receipt, note: str) -> None:
    category = _category_marker(receipt.caption_text)
    receipt.caption_text = _caption_text(note=note, category=category)


def _set_receipt_category(receipt: Receipt, category: str) -> None:
    receipt.caption_text = _caption_text(
        note=receipt_caption_note(receipt),
        category=category,
    )


def _caption_text(*, note: str | None, category: str | None) -> str | None:
    parts = []
    if note:
        parts.append(note)
    if category:
        parts.append(f"[kategori:{category}]")
    return " ".join(parts) or None


def _category_name_from_alias(value: str) -> str:
    normalized = _clean_edit_value(value).lower()
    aliases = {
        "makan": "Makanan",
        "makanan": "Makanan",
        "kopi": "Makanan",
        "transport": "Transportasi",
        "transportasi": "Transportasi",
        "bensin": "Transportasi",
        "tagihan": "Tagihan",
        "kos": "Tagihan",
        "belanja": "Belanja",
        "hiburan": "Hiburan",
        "kesehatan": "Kesehatan",
        "pendidikan": "Pendidikan",
    }
    return aliases.get(normalized, normalized.title())


def _clean_edit_value(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" -,.")
