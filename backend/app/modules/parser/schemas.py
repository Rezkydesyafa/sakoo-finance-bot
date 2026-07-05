from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any


SOURCE_WHATSAPP_TEXT = "whatsapp_text"
CONFIRMATION_THRESHOLD = 0.85

INTENT_ADD_TRANSACTION = "add_transaction"
INTENT_GET_BALANCE = "get_balance"
INTENT_LIST_EXPENSE = "list_expense"
INTENT_LIST_INCOME = "list_income"
INTENT_GET_REPORT = "get_report"
INTENT_EXPORT_PDF = "export_pdf"
INTENT_HELP = "help"
INTENT_LINK_ACCOUNT = "link_account"
INTENT_UNKNOWN = "unknown"

# Existing public intent kept for backward compatibility with earlier tests/flows.
INTENT_RECENT_TRANSACTIONS = "recent_transactions"
INTENT_DELETE_LAST_TRANSACTION = "delete_last_transaction"

VALID_INTENTS = {
    INTENT_ADD_TRANSACTION,
    INTENT_GET_BALANCE,
    INTENT_LIST_EXPENSE,
    INTENT_LIST_INCOME,
    INTENT_GET_REPORT,
    INTENT_EXPORT_PDF,
    INTENT_HELP,
    INTENT_LINK_ACCOUNT,
    INTENT_UNKNOWN,
    INTENT_RECENT_TRANSACTIONS,
    INTENT_DELETE_LAST_TRANSACTION,
}

TRANSACTION_TYPES = {"income", "expense", "none"}

# ── Centralized keyword sets ──────────────────────────────────────────
# Shared by intent_router and transaction_parser so there is a single
# source of truth for language detection.

INCOME_KEYWORDS: frozenset[str] = frozenset({
    "bonus", "cashback", "dapat", "dapet", "dibayar", "freelance",
    "gaji", "income", "masuk", "pemasukan", "pendapatan", "refund",
    "salary", "terima", "upah",
})

INCOME_PHRASES: tuple[str, ...] = ("transfer masuk", "uang saku", "uang jajan")

EXPENSE_KEYWORDS: frozenset[str] = frozenset({
    "bayar", "beli", "belanja", "biaya", "checkout", "habis",
    "jajan", "keluar", "langganan", "makan", "minum", "topup",
    "transfer", "untuk",
})

CATEGORY_HINTS: frozenset[str] = frozenset({
    "ayam", "bensin", "bioskop", "buku", "bus", "dokter", "game",
    "gofood", "gojek", "grab", "grabfood", "internet", "cafe",
    "kelas", "klinik", "kopi", "kos", "kursus", "listrik", "nasi",
    "netflix", "obat", "parkir", "pulsa", "seblak", "shopee",
    "spotify", "tokopedia", "tol", "ukt", "wifi", "tugas", "dana",
    "gopay", "ovo",
})


@dataclass(frozen=True)
class ParsedTransactionText:
    intent: str
    type: str | None
    amount: Decimal | None
    category: str | None
    description: str | None
    transaction_date: date | None
    source: str
    confidence: float
    need_confirmation: bool
    reasons: list[str]
    period: str | None = None

    def to_log_payload(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "type": self.type,
            "amount": str(self.amount) if self.amount is not None else None,
            "category": self.category,
            "description": self.description,
            "transaction_date": self.transaction_date.isoformat()
            if self.transaction_date
            else None,
            "source": self.source,
            "confidence": self.confidence,
            "need_confirmation": self.need_confirmation,
            "reasons": self.reasons,
            "period": self.period,
        }


@dataclass(frozen=True)
class AmountMatch:
    value: Decimal
    start: int
    end: int
    score: float


@dataclass(frozen=True)
class DateMatch:
    value: date
    start: int
    end: int
    explicit: bool
    period_code: str | None = None


@dataclass(frozen=True)
class IntentMatch:
    intent: str
    period: str | None = None
    confidence: float = 1.0
