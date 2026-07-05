"""Ollama-based AI transaction parser.

Uses a local Ollama instance with the model configured in settings.
to parse natural-language messages into structured transaction data.  This
module acts as a **fallback** when the rule-based parser produces a low
confidence score.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.modules.parser.service import ParsedMessage

logger = logging.getLogger(__name__)

# Valid categories that the model can choose from.
VALID_CATEGORIES = [
    "Makanan",
    "Transportasi",
    "Tagihan",
    "Belanja",
    "Hiburan",
    "Kesehatan",
    "Pendidikan",
    "Gaji",
    "Tabungan",
    "Lainnya",
]

TRANSACTION_PARSE_PROMPT_TEMPLATE = """Kamu adalah parser transaksi keuangan. Ubah pesan pengguna menjadi JSON transaksi.

ATURAN:
1. Tentukan "intent": salah satu dari "add_transaction", "get_report", "export_pdf", "get_balance", "recent_transactions", "delete_last_transaction", "help", "unknown"
2. Jika intent adalah "add_transaction":
   - "type": "expense" untuk pengeluaran, "income" untuk pemasukan
   - "amount": angka bulat dalam Rupiah (contoh: "20 ribu" = 20000, "2 juta" = 2000000, "30rb" = 30000)
   - "category": salah satu dari {categories}
   - "description": deskripsi singkat transaksi
   - "transaction_date": tanggal dalam format YYYY-MM-DD. Hari ini: {today}. Jika "kemarin" kurangi 1 hari. Jika tidak disebutkan, gunakan hari ini.
3. Jika intent bukan "add_transaction", isi field lain dengan null

FORMAT OUTPUT (HANYA JSON, TANPA PENJELASAN):
{{"intent":"...","type":"...","amount":angka,"category":"...","description":"...","transaction_date":"YYYY-MM-DD"}}

PESAN: "{message}"
"""


def ollama_available(settings: Settings | None = None) -> bool:
    """Check whether the Ollama server is reachable."""
    active_settings = settings or get_settings()
    if not active_settings.ollama_base_url.strip():
        return False
    try:
        response = httpx.get(
            f"{active_settings.ollama_base_url.rstrip('/')}/api/tags",
            timeout=5.0,
        )
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def parse_with_ollama(
    text: str,
    source: str,
    *,
    today: date | None = None,
    settings: Settings | None = None,
) -> ParsedMessage | None:
    """Parse a natural-language message into a ``ParsedMessage`` using Ollama.

    Returns ``None`` when the Ollama server is unreachable, the model fails to
    produce valid JSON, or the result cannot be mapped to a ``ParsedMessage``.
    """
    active_settings = settings or get_settings()
    base_url = active_settings.ollama_base_url.rstrip("/")
    model = active_settings.ollama_model
    timeout = active_settings.ollama_timeout_seconds

    if not base_url:
        return None

    today_date = today or date.today()
    prompt = TRANSACTION_PARSE_PROMPT_TEMPLATE.format(
        categories=", ".join(VALID_CATEGORIES),
        today=today_date.isoformat(),
        message=text.strip()[:500],
    )

    try:
        response = httpx.post(
            f"{base_url}/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 256,
            },
            timeout=timeout,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        logger.warning("Ollama AI parser request failed: %s", exc)
        return None
    except ValueError:
        logger.warning("Ollama AI parser returned invalid JSON response")
        return None

    # Extract text from OpenAI-compatible response format.
    try:
        raw_text = str(data["choices"][0]["message"]["content"]).strip()
    except (KeyError, IndexError, TypeError):
        logger.warning("Ollama AI parser response missing text content")
        return None

    return _parse_ollama_response(raw_text, source=source, today=today_date)


def _parse_ollama_response(
    raw_text: str,
    *,
    source: str,
    today: date,
) -> ParsedMessage | None:
    """Extract and validate the JSON from the model output."""

    # Try to find JSON in the response (model may include extra text).
    json_match = re.search(r"\{[^{}]+\}", raw_text)
    if not json_match:
        logger.warning("Ollama AI parser: no JSON object found in response")
        return None

    try:
        parsed: dict[str, Any] = json.loads(json_match.group())
    except json.JSONDecodeError:
        logger.warning("Ollama AI parser: failed to decode JSON")
        return None

    intent = str(parsed.get("intent", "unknown")).strip()
    if intent not in {
        "add_transaction",
        "get_report",
        "export_pdf",
        "get_balance",
        "recent_transactions",
        "delete_last_transaction",
        "help",
        "unknown",
    }:
        intent = "unknown"

    txn_type = parsed.get("type")
    if txn_type not in ("income", "expense", None):
        txn_type = None

    amount = _safe_decimal(parsed.get("amount"))
    category = parsed.get("category")
    if category not in VALID_CATEGORIES:
        category = "Lainnya" if intent == "add_transaction" else None

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
    need_confirmation = confidence < 0.85 or amount is None or txn_type is None

    period: str | None = None
    if intent in ("get_report", "export_pdf"):
        period = parsed.get("period")

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
        reasons=["ai_ollama_parser"],
        period=period,
        category_confidence=confidence if category else None,
        category_source="ai_ollama" if category else None,
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
