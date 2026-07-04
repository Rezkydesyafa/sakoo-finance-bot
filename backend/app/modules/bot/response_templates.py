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
        "Halo, aku Sakoo.\n"
        "Aku bisa bantu catat dan cek keuangan kamu lewat chat.\n\n"
        "Contoh catat transaksi:\n"
        "- beli makan 20 ribu\n"
        "- bayar bensin 30rb\n"
        "- gaji masuk 2 juta\n"
        "- dapet uang saku 100k\n\n"
        "Cek laporan:\n"
        "- saldo\n"
        "- list pengeluaran\n"
        "- list pemasukan\n"
        "- laporan bulan ini\n"
        "- export laporan bulan ini\n\n"
        "Command:\n"
        "- /saldo\n"
        "- /laporan\n"
        "- /export\n"
        "- /help"
    )


def format_saved_transaction(
    transaction: TransactionLike,
    category: CategoryLike | None,
    *,
    style: str = "friendly",
    balance_after: Decimal | None = None,
    context_note: str | None = None,
) -> str:
    direction = "Pemasukan" if transaction.type == "income" else "Pengeluaran"
    title = "Pemasukan tercatat!" if transaction.type == "income" else "Transaksi Tercatat!"
    category_name = category.name if category else "Tanpa kategori"
    description = transaction.description or "-"
    balance_line = f"\nSaldo sekarang: {format_rupiah(balance_after)}" if balance_after is not None else ""
    note_line = f"\n\n{context_note}" if context_note else ""

    if style == "short":
        return (
            "Oke, Tercatat.\n"
            f"{direction} {format_rupiah(transaction.amount)} - {category_name}"
            f"{balance_line}"
        )

    if style == "detailed":
        return (
            f"{title}\n\n"
            f"Jenis: {direction}\n"
            f"Nominal: {format_rupiah(transaction.amount)}\n"
            f"Kategori: {category_name}\n"
            f"Catatan: {description}\n"
            f"Tanggal: {format_date_label(transaction.transaction_date)}"
            f"{balance_line}{note_line}"
        )

    return (
        f"{title}\n\n"
        f"Jenis: {direction}\n"
        f"Nominal: {format_rupiah(transaction.amount)}\n"
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
            "Aku belum menemukan nominalnya (nominal belum terbaca).\n\n"
            "Contoh:\n"
            "- beli kopi 18 ribu\n"
            "- bayar bensin 30rb\n"
            "- gaji masuk 2 juta"
        )

    direction = _format_transaction_type(transaction_type)
    amount_label = format_rupiah(amount) if amount else "nominal belum terbaca"
    category_label = category or "kategori belum terbaca"
    date_label = format_date_label(transaction_date)
    description_label = description or "-"
    return (
        "Saya belum yakin membaca transaksinya. Aku membaca ini sebagai:\n\n"
        f"Jenis: {direction}\n"
        f"Nominal: {amount_label}\n"
        f"Kategori: {category_label}\n"
        f"Tanggal: {date_label}\n"
        f"Catatan: {description_label}\n\n"
        "Balas YA untuk simpan, atau koreksi: edit kategori transport / "
        "edit tanggal kemarin / edit catatan makan siang."
    )


def format_unknown_response() -> str:
    return (
        "Aku belum paham maksudnya.\n\n"
        "Coba kirim seperti:\n"
        "- beli kopi 18 ribu\n"
        "- saldo\n"
        "- laporan bulan ini\n"
        "- bulan ini aku boros gak?\n"
        "- /help"
    )


def format_cancelled_response() -> str:
    return "Oke, aku batalin. Tidak ada transaksi yang disimpan."


def format_no_pending_response() -> str:
    return "Belum ada transaksi yang menunggu konfirmasi, atau konfirmasi lama sudah kedaluwarsa."


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
