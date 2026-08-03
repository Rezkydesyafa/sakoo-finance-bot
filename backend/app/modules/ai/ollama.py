"""Shared prompt and validation helpers for LLM transaction parsing."""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.modules.parser.service import ParsedMessage

logger = logging.getLogger(__name__)

TRANSACTION_PARSE_SYSTEM_PROMPT = """Kamu adalah interpreter pesan untuk aplikasi keuangan Sakoo.
Keluarkan tepat satu object JSON tanpa markdown atau penjelasan."""

TRANSACTION_PARSE_PROMPT_TEMPLATE = """Ubah pesan pengguna menjadi JSON terstruktur.

ATURAN:
1. Tentukan "intent": salah satu dari "add_transaction", "get_report", "export_pdf", "get_balance", "recent_transactions", "delete_last_transaction", "list_expense", "list_income", "sorted_expense", "category_detail", "create_category", "help", "finance_chat", "unknown"
2. Jika intent adalah "add_transaction":
   - "type": "expense" untuk pengeluaran, "income" untuk pemasukan
   - "amount": angka bulat dalam Rupiah (contoh: "20 ribu" = 20000, "2 juta" = 2000000, "30rb" = 30000)
   - "category": nama dari daftar kategori valid yang tipenya sesuai transaksi
   - "description": deskripsi singkat transaksi
   - "transaction_date": tanggal dalam format YYYY-MM-DD. Hari ini: {today}. Jika "kemarin" kurangi 1 hari. Jika tidak disebutkan, gunakan hari ini.
3. Jika intent "list_expense" atau "list_income": isi "period" (day/week/month/yesterday) dan "limit" (angka jika disebutkan)
4. Jika intent "sorted_expense": isi "period" dan "sort_order" (desc/asc/date_desc/date_asc)
5. Jika intent "category_detail": isi "category_filter" dengan nama kategori valid yang ditanya
6. Jika intent "create_category": isi "category" dengan nama kategori baru
7. Jika intent lainnya, isi field yang tidak relevan dengan null

KATEGORI VALID (JSON):
{categories}

FORMAT OUTPUT:
{{"intent":"...","type":"...","amount":angka,"category":"...","description":"...","transaction_date":"YYYY-MM-DD","period":"...","limit":angka,"sort_order":"...","category_filter":"..."}}

PESAN PENGGUNA (JSON): {message}
"""

SUPPORTED_INTENTS = {
    "add_transaction",
    "get_report",
    "export_pdf",
    "get_balance",
    "recent_transactions",
    "delete_last_transaction",
    "list_expense",
    "list_income",
    "sorted_expense",
    "category_detail",
    "create_category",
    "help",
    "finance_chat",
    "unknown",
}
VALID_PERIODS = {"day", "week", "month", "yesterday"}
VALID_SORT_ORDERS = {"desc", "asc", "date_desc", "date_asc"}


def build_transaction_parse_prompt(
    text: str,
    *,
    today: date,
    category_options: Sequence[tuple[str, str]],
) -> str:
    categories = [
        {"name": name, "type": transaction_type}
        for name, transaction_type in category_options
    ]
    return TRANSACTION_PARSE_PROMPT_TEMPLATE.format(
        categories=json.dumps(categories, ensure_ascii=False),
        today=today.isoformat(),
        message=json.dumps(text.strip()[:500], ensure_ascii=False),
    )


def parse_transaction_response(
    raw_text: str,
    *,
    source: str,
    today: date,
    category_options: Sequence[tuple[str, str]],
    provider_name: str,
) -> ParsedMessage | None:
    """Extract and validate a provider's structured transaction JSON."""

    json_start = raw_text.find("{")
    if json_start < 0:
        logger.warning("%s LLM parser: no JSON object found", provider_name)
        return None

    try:
        decoded, _end = json.JSONDecoder().raw_decode(raw_text[json_start:])
    except json.JSONDecodeError:
        logger.warning("%s LLM parser: failed to decode JSON", provider_name)
        return None
    if not isinstance(decoded, dict):
        return None
    parsed: dict[str, Any] = decoded

    intent = str(parsed.get("intent", "unknown")).strip()
    if intent not in SUPPORTED_INTENTS:
        intent = "unknown"

    txn_type = parsed.get("type")
    if txn_type not in ("income", "expense", None):
        txn_type = None

    amount = _safe_decimal(parsed.get("amount"))
    category = _match_category(
        parsed.get("category"),
        transaction_type=txn_type,
        category_options=category_options,
    )
    if intent == "add_transaction" and category is None:
        category = "Lainnya"

    description = parsed.get("description")
    if description is not None:
        description = str(description).strip()[:200] or None

    transaction_date = _safe_date(parsed.get("transaction_date"), fallback=today)

    # Calculate confidence based on how many fields were successfully extracted.
    confidence = _calculate_ai_confidence(
        intent=intent,
        txn_type=txn_type,
        amount=amount,
        category=category,
        description=description,
    )
    need_confirmation = (
        confidence < 0.85
        or amount is None
        or txn_type is None
        or category == "Lainnya"
    )
    period = _safe_choice(parsed.get("period"), VALID_PERIODS)
    sort_order = _safe_choice(parsed.get("sort_order"), VALID_SORT_ORDERS)
    limit = _safe_limit(parsed.get("limit"))
    category_filter = _match_category(
        parsed.get("category_filter")
        or (parsed.get("category") if intent == "category_detail" else None),
        transaction_type=None,
        category_options=category_options,
    )

    parser_reason = (
        "ai_ollama_parser"
        if provider_name == "ollama"
        else f"llm_{provider_name}_parser"
    )
    category_source = (
        "ai_ollama" if provider_name == "ollama" else f"llm_{provider_name}"
    )
    return ParsedMessage(
        intent=intent,
        type=txn_type,
        amount=amount,
        category=category,
        description=description,
        transaction_date=transaction_date,
        source=source,
        confidence=confidence,
        need_confirmation=need_confirmation,
        reasons=[parser_reason],
        period=period,
        category_confidence=confidence if category else None,
        category_source=category_source if category else None,
        limit=limit,
        sort_order=sort_order,
        category_filter=category_filter,
    )


def _safe_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        d = Decimal(str(value))
        return d if d > 0 else None
    except (InvalidOperation, ValueError, TypeError):
        return None


def _safe_date(value: Any, *, fallback: date) -> date:
    if value is None:
        return fallback
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return fallback


def _match_category(
    value: Any,
    *,
    transaction_type: str | None,
    category_options: Sequence[tuple[str, str]],
) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().casefold()
    for name, category_type in category_options:
        if name.casefold() == normalized and (
            transaction_type is None
            or category_type in {transaction_type, "both"}
        ):
            return name
    return None


def _safe_choice(value: Any, choices: set[str]) -> str | None:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in choices else None


def _safe_limit(value: Any) -> int | None:
    try:
        limit = int(value)
    except (TypeError, ValueError):
        return None
    return min(limit, 50) if limit > 0 else None


def _calculate_ai_confidence(
    *,
    intent: str,
    txn_type: str | None,
    amount: Decimal | None,
    category: str | None,
    description: str | None,
) -> float:
    """Score the AI result based on how many key fields it was able to extract."""
    if intent != "add_transaction":
        return 0.90

    score = 0.10  # base
    if amount is not None:
        score += 0.35
    if txn_type is not None:
        score += 0.20
    if category and category != "Lainnya":
        score += 0.20
    if description:
        score += 0.10
    # date is always present (fallback to today), so give a small bonus
    score += 0.05

    return round(min(max(score, 0.0), 1.0), 4)
