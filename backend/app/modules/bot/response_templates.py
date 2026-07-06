from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Protocol


class TransactionLike(Protocol):
    type: str
    amount: Decimal | None
    description: str | None
    transaction_date: date


class CategoryLike(Protocol):
    name: str


def format_help_response() -> str:
    return (
        "👋 Halo, aku *Sakoo*!\n"
        "Asisten keuangan pribadimu lewat chat 💰\n\n"
        "✏️ *Catat transaksi:*\n"
        "• beli makan 20 ribu\n"
        "• bayar bensin 30rb\n"
        "• gaji masuk 2 juta\n"
        "• dapet uang saku 100k\n\n"
        "📊 *Cek laporan:*\n"
        "• saldo\n"
        "• list pengeluaran\n"
        "• list pemasukan\n"
        "• laporan bulan ini\n"
        "• export laporan bulan ini\n\n"
        "💡 *Tanya keuangan:*\n"
        "• tips menabung\n"
        "• cara mengatur keuangan\n"
        "• bulan ini aku boros gak?\n\n"
        "⚡ *Command:*\n"
        "• /saldo\n"
        "• /laporan\n"
        "• /export\n"
        "• /help\n\n"
        "Yuk mulai catat keuanganmu! 🚀"
    )


def format_saved_transaction(
    transaction: TransactionLike,
    category: CategoryLike | None,
    *,
    style: str = "friendly",
    balance_after: Decimal | None = None,
    context_note: str | None = None,
) -> str:
    is_income = transaction.type == "income"
    emoji = "💰" if is_income else "💸"
    direction = "Pemasukan" if is_income else "Pengeluaran"
    title = f"{emoji} Pemasukan tercatat!" if is_income else f"{emoji} Transaksi Tercatat!"
    category_name = category.name if category else "Tanpa kategori"
    description = transaction.description or "-"
    balance_line = f"\n💳 Saldo sekarang: *{format_rupiah(balance_after)}*" if balance_after is not None else ""
    note_line = f"\n\n📌 {context_note}" if context_note else ""

    if style == "short":
        return (
            "✅ Tercatat.\n"
            f"{direction} *{format_rupiah(transaction.amount)}* — {category_name}"
            f"{balance_line}"
        )

    if style == "detailed":
        return (
            f"{title}\n\n"
            f"Jenis: {direction}\n"
            f"Nominal: *{format_rupiah(transaction.amount)}*\n"
            f"Kategori: {category_name}\n"
            f"Catatan: {description}\n"
            f"Tanggal: {format_date_label(transaction.transaction_date)}"
            f"{balance_line}{note_line}"
        )

    return (
        f"{title}\n\n"
        f"Jenis: {direction}\n"
        f"Nominal: *{format_rupiah(transaction.amount)}*\n"
        f"Kategori: {category_name}\n"
        f"Catatan: {description}\n"
        f"Tanggal: {format_date_label(transaction.transaction_date)}"
        f"{balance_line}{note_line}"
    )


def format_confirmation_request(
    *,
    transaction_type: str | None,
    amount: Decimal | None,
    category: str | None,
    transaction_date: date | None = None,
    description: str | None = None,
    missing_amount: bool,
) -> str:
    if missing_amount:
        return (
            "⚠️ Aku belum menemukan nominalnya.\n\n"
            "Contoh:\n"
            "• beli kopi 18 ribu\n"
            "• bayar bensin 30rb\n"
            "• gaji masuk 2 juta"
        )

    direction = _format_transaction_type(transaction_type)
    amount_label = format_rupiah(amount) if amount else "nominal belum terbaca"
    category_label = category or "kategori belum terbaca"
    date_label = format_date_label(transaction_date)
    description_label = description or "-"
    return (
        "🤔 Aku belum yakin membaca transaksinya:\n\n"
        f"Jenis: {direction}\n"
        f"Nominal: *{amount_label}*\n"
        f"Kategori: {category_label}\n"
        f"Tanggal: {date_label}\n"
        f"Catatan: {description_label}\n\n"
        "Balas *YA* untuk simpan, atau koreksi:\n"
        "_edit kategori transport_\n"
        "_edit tanggal kemarin_\n"
        "_edit catatan makan siang_"
    )


def format_unknown_response() -> str:
    return (
        "Hmm, aku belum paham maksudnya 🤔\n\n"
        "Coba tanya seputar keuangan, misalnya:\n"
        "• 💡 tips menabung\n"
        "• 📊 laporan bulan ini\n"
        "• 💰 saldo\n"
        "• ✍️ beli kopi 18rb\n\n"
        "Ketik /help untuk lihat semua fitur! 😊"
    )


def format_llm_error_response() -> str:
    """Shown when LLM provider fails (API error, timeout, etc.)."""
    return (
        "😅 Ups, aku lagi ada gangguan nih.\n"
        "Coba lagi dalam beberapa saat ya!\n\n"
        "Sementara itu, kamu bisa pakai:\n"
        "• 💰 saldo\n"
        "• 📊 laporan bulan ini\n"
        "• /help"
    )


def format_rate_limit_response() -> str:
    """Shown when user hits daily LLM request limit."""
    return (
        "⏳ Kamu sudah mencapai batas chat harian.\n"
        "Kuota akan reset besok.\n\n"
        "Kamu masih bisa pakai perintah langsung:\n"
        "• saldo\n"
        "• list pengeluaran\n"
        "• laporan bulan ini"
    )


def format_cancelled_response() -> str:
    return "❌ Oke, aku batalin. Tidak ada transaksi yang disimpan."


def format_no_pending_response() -> str:
    return "ℹ️ Belum ada transaksi yang menunggu konfirmasi, atau konfirmasi lama sudah kedaluwarsa."


def format_rupiah(value: Decimal | int | None) -> str:
    if value is None:
        return "Rp0"
    return f"Rp{int(value):,}".replace(",", ".")


def format_date_label(value: date | None) -> str:
    if value is None:
        return "-"
    if value == date.today():
        return "Hari ini"
    return value.isoformat()


def _format_transaction_type(transaction_type: str | None) -> str:
    if transaction_type == "income":
        return "Pemasukan"
    if transaction_type == "expense":
        return "Pengeluaran"
    return "tipe belum terbaca"
