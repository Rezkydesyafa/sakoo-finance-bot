from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Category, Transaction
from app.modules.parser.service import ParsedMessage, parse_message
from app.modules.parser.transaction_text import (
    INTENT_ADD_TRANSACTION,
)


@dataclass(frozen=True)
class TextTransactionResult:
    status: str
    reply_text: str
    parse_result: ParsedMessage
    transaction_id: int | None = None
    error_message: str | None = None

    def to_log_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["parse_result"] = self.parse_result.to_log_payload()
        return payload


def handle_whatsapp_text_transaction(
    *,
    db: Session,
    user_id: int,
    text: str,
) -> TextTransactionResult:
    parse_result = parse_message(text, source="whatsapp_text")
    if parse_result.intent != INTENT_ADD_TRANSACTION:
        return TextTransactionResult(
            status=parse_result.intent,
            reply_text=_format_command_response(parse_result),
            parse_result=parse_result,
        )

    if parse_result.need_confirmation:
        return TextTransactionResult(
            status="needs_confirmation",
            reply_text=_format_confirmation_request(parse_result),
            parse_result=parse_result,
            error_message="low_confidence_parser",
        )

    category = _find_category(
        db=db,
        category_name=parse_result.category,
        transaction_type=parse_result.type,
    )
    transaction = Transaction(
        user_id=user_id,
        type=parse_result.type,
        amount=parse_result.amount,
        category_id=category.id if category else None,
        description=parse_result.description,
        transaction_date=parse_result.transaction_date,
        source=parse_result.source,
    )
    db.add(transaction)
    db.flush()

    return TextTransactionResult(
        status="saved",
        reply_text=_format_saved_transaction(transaction, category),
        parse_result=parse_result,
        transaction_id=transaction.id,
    )


def _find_category(
    *,
    db: Session,
    category_name: str | None,
    transaction_type: str | None,
) -> Category | None:
    if not transaction_type:
        return None

    names_to_try = [category_name]
    names_to_try.append("Gaji" if transaction_type == "income" else "Lainnya")

    for name in [item for item in names_to_try if item]:
        category = db.scalar(
            select(Category).where(
                func.lower(Category.name) == name.lower(),
                Category.type == transaction_type,
            )
        )
        if category:
            return category

    return None


def _format_command_response(parse_result: ParsedMessage) -> str:
    period = _format_period(parse_result.period)

    if parse_result.intent == "get_report":
        return f"Perintah laporan {period} terdeteksi. Report service akan memproses permintaan ini."
    if parse_result.intent == "export_pdf":
        return f"Perintah export PDF laporan {period} terdeteksi. PDF service akan memproses permintaan ini."
    if parse_result.intent == "recent_transactions":
        return "Perintah riwayat transaksi terdeteksi. Bot akan menampilkan transaksi terbaru."
    if parse_result.intent == "delete_last_transaction":
        return "Perintah hapus transaksi terakhir terdeteksi. Bot akan meminta konfirmasi sebelum menghapus."
    if parse_result.intent == "help":
        return (
            "Panduan: kirim transaksi seperti 'beli makan 20 ribu', "
            "'gaji masuk 2 juta', 'laporan bulan ini', atau 'export laporan bulan ini'."
        )
    return "Perintah terdeteksi."


def _format_period(period: str | None) -> str:
    labels = {
        "day": "hari ini",
        "week": "minggu ini",
        "month": "bulan ini",
        "yesterday": "kemarin",
    }
    return labels.get(period or "", "default")


def _format_saved_transaction(
    transaction: Transaction,
    category: Category | None,
) -> str:
    direction = "Pemasukan" if transaction.type == "income" else "Pengeluaran"
    category_name = category.name if category else "Tanpa kategori"
    description = f" ({transaction.description})" if transaction.description else ""
    return (
        f"Tercatat: {direction} {_format_rupiah(transaction.amount)} "
        f"untuk {category_name}{description} pada {transaction.transaction_date.isoformat()}."
    )


def _format_confirmation_request(parse_result: ParsedMessage) -> str:
    amount = _format_rupiah(parse_result.amount) if parse_result.amount else "nominal belum terbaca"
    category = parse_result.category or "kategori belum terbaca"
    transaction_type = parse_result.type or "tipe belum terbaca"
    return (
        "Saya belum yakin membaca transaksi ini. "
        f"Terbaca sementara: {transaction_type}, {amount}, {category}. "
        "Kirim ulang dengan format lebih jelas, contoh: beli kopi 18 ribu."
    )


def _format_rupiah(value: Decimal | None) -> str:
    if value is None:
        return "Rp0"
    return f"Rp{int(value):,}".replace(",", ".")
