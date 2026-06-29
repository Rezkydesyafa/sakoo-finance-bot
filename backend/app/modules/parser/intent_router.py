from __future__ import annotations

import re

from app.modules.parser.amount_parser import extract_amount
from app.modules.parser.date_parser import detect_period
from app.modules.parser.normalizer import normalize_text
from app.modules.parser.schemas import (
    INTENT_ADD_TRANSACTION,
    INTENT_DELETE_LAST_TRANSACTION,
    INTENT_EXPORT_PDF,
    INTENT_GET_BALANCE,
    INTENT_GET_REPORT,
    INTENT_HELP,
    INTENT_LINK_ACCOUNT,
    INTENT_LIST_EXPENSE,
    INTENT_LIST_INCOME,
    INTENT_RECENT_TRANSACTIONS,
    INTENT_UNKNOWN,
    IntentMatch,
)


HELP_KEYWORDS = {"bantuan", "help", "menu", "panduan", "mulai", "start"}
BALANCE_PHRASES = (
    "saldo",
    "saldo saya",
    "sisa saldo",
    "uang tersisa",
    "sisa uang",
)
REPORT_KEYWORDS = {"laporan", "rekap", "ringkasan"}
EXPORT_KEYWORDS = {"download", "ekspor", "export", "pdf", "unduh"}
LIST_EXPENSE_PHRASES = (
    "list pengeluaran",
    "daftar pengeluaran",
    "pengeluaran bulan ini",
    "pengeluaran minggu ini",
    "pengeluaran hari ini",
)
LIST_INCOME_PHRASES = (
    "list pemasukan",
    "daftar pemasukan",
    "pemasukan bulan ini",
    "pemasukan minggu ini",
    "pemasukan hari ini",
)
RECENT_TRANSACTION_PHRASES = (
    "riwayat",
    "riwayat transaksi",
    "daftar transaksi",
    "transaksi terbaru",
    "transaksi terakhir",
)
DELETE_LAST_PHRASES = (
    "hapus transaksi terakhir",
    "delete transaksi terakhir",
    "batalkan transaksi terakhir",
)
LINK_ACCOUNT_PHRASES = ("hubungkan", "link akun", "sambungkan")

COMMAND_INTENTS = {
    "/start": INTENT_HELP,
    "/help": INTENT_HELP,
    "/saldo": INTENT_GET_BALANCE,
    "/laporan": INTENT_GET_REPORT,
    "/export": INTENT_EXPORT_PDF,
    "/pengeluaran": INTENT_LIST_EXPENSE,
    "/pemasukan": INTENT_LIST_INCOME,
    "/riwayat": INTENT_RECENT_TRANSACTIONS,
}

INCOME_KEYWORDS = {
    "bonus",
    "cashback",
    "dapat",
    "dapet",
    "dibayar",
    "freelance",
    "gaji",
    "income",
    "masuk",
    "pemasukan",
    "pendapatan",
    "refund",
    "salary",
    "terima",
    "upah",
}
INCOME_PHRASES = ("transfer masuk", "uang saku", "uang jajan")
EXPENSE_KEYWORDS = {
    "bayar",
    "beli",
    "belanja",
    "biaya",
    "checkout",
    "habis",
    "jajan",
    "keluar",
    "langganan",
    "makan",
    "minum",
    "topup",
    "transfer",
    "untuk",
}
CATEGORY_HINTS = {
    "ayam",
    "bensin",
    "bioskop",
    "buku",
    "bus",
    "dokter",
    "game",
    "gofood",
    "gojek",
    "grab",
    "grabfood",
    "internet",
    "cafe",
    "kelas",
    "klinik",
    "kopi",
    "kos",
    "kursus",
    "listrik",
    "nasi",
    "netflix",
    "obat",
    "parkir",
    "pulsa",
    "seblak",
    "shopee",
    "spotify",
    "tokopedia",
    "tol",
    "ukt",
    "wifi",
    "tugas",
    "dana",
    "gopay",
    "ovo",
}


def detect_intent(text: str) -> IntentMatch:
    normalized = normalize_text(text)
    tokens = _tokenize(normalized)
    period = detect_period(normalized)

    if _looks_like_transaction_input(normalized):
        return IntentMatch(intent=INTENT_ADD_TRANSACTION, confidence=0.95)

    command = _extract_command(normalized)
    if command:
        intent = COMMAND_INTENTS.get(command, INTENT_UNKNOWN)
        return IntentMatch(intent=intent, period=period, confidence=1.0)

    if tokens & HELP_KEYWORDS and len(tokens) <= 4:
        return IntentMatch(intent=INTENT_HELP, confidence=1.0)
    if _contains_phrase(normalized, LINK_ACCOUNT_PHRASES):
        return IntentMatch(intent=INTENT_LINK_ACCOUNT, confidence=0.95)
    if _contains_phrase(normalized, DELETE_LAST_PHRASES):
        return IntentMatch(intent=INTENT_DELETE_LAST_TRANSACTION, confidence=1.0)
    if _contains_phrase(normalized, LIST_EXPENSE_PHRASES):
        return IntentMatch(intent=INTENT_LIST_EXPENSE, period=period, confidence=1.0)
    if _contains_phrase(normalized, LIST_INCOME_PHRASES):
        return IntentMatch(intent=INTENT_LIST_INCOME, period=period, confidence=1.0)
    if _contains_phrase(normalized, RECENT_TRANSACTION_PHRASES):
        return IntentMatch(intent=INTENT_RECENT_TRANSACTIONS, period=period, confidence=1.0)
    if _contains_phrase(normalized, BALANCE_PHRASES):
        return IntentMatch(intent=INTENT_GET_BALANCE, confidence=1.0)
    if (tokens & EXPORT_KEYWORDS) and (tokens & REPORT_KEYWORDS):
        return IntentMatch(intent=INTENT_EXPORT_PDF, period=period, confidence=1.0)
    if tokens & REPORT_KEYWORDS:
        return IntentMatch(intent=INTENT_GET_REPORT, period=period, confidence=1.0)

    if _has_transaction_language(normalized):
        return IntentMatch(intent=INTENT_ADD_TRANSACTION, confidence=0.75)

    return IntentMatch(intent=INTENT_UNKNOWN, confidence=0.25)


def _looks_like_transaction_input(text: str) -> bool:
    if extract_amount(text) is None:
        return False
    return _has_transaction_language(text)


def _has_transaction_language(text: str) -> bool:
    tokens = _tokenize(text)
    if tokens & INCOME_KEYWORDS:
        return True
    if tokens & EXPENSE_KEYWORDS:
        return True
    if tokens & CATEGORY_HINTS:
        return True
    return any(phrase in text for phrase in INCOME_PHRASES)


def _extract_command(text: str) -> str | None:
    match = re.match(r"^(/[a-zA-Z]+)\b", text)
    return match.group(1).lower() if match else None


def _contains_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z\u00c0-\u024f]+", text.lower()))
