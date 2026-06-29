from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from app.modules.parser.schemas import (
    CATEGORY_CODE_MAP,
    COMPACT_INTENT_MAP,
    DATE_CODE_MAP,
    INTENT_ADD_TRANSACTION,
)


LLM_PROMPT_TEMPLATE = """Parse pesan ke JSON saja.

Cat:
MKN makanan, TRP transport, TGH tagihan, BLJ belanja, HBR hiburan, KSH kesehatan, PDD pendidikan, GJI gaji, USK uang_saku, LNY lainnya.

Intent:
ADD transaksi, BAL saldo, EXP pengeluaran, INC pemasukan, REP laporan, PDF export_pdf, HELP bantuan, UNK unknown.

JSON:
{"i":"","t":"","a":0,"c":"","d":"","dt":"","cf":0,"ask":false}

Rule:
i pakai kode intent. t=income/expense/none. a=rupiah integer. c=kode cat. dt=today/yesterday/this_week/this_month/unknown. Jika ragu/nominal kosong ask=true cf rendah. Jangan tambah teks.

Msg: "{message}"
"""


class LlmProviderError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class LlmResponseValidationError(LlmProviderError):
    pass


@dataclass(frozen=True)
class LlmProviderConfig:
    api_key: str
    timeout_seconds: float


class BaseLlmProvider(ABC):
    provider_name: str

    def __init__(self, config: LlmProviderConfig) -> None:
        self.config = config

    @abstractmethod
    def parse_transaction(self, message: str) -> dict[str, Any]:
        """Return compact validated LLM JSON."""


def build_llm_prompt(message: str) -> str:
    compact_message = re.sub(r"\s+", " ", message.strip())
    escaped_message = compact_message[:500].replace("\\", "\\\\").replace('"', '\\"')
    return LLM_PROMPT_TEMPLATE.replace("{message}", escaped_message)


def parse_json_object(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise LlmResponseValidationError("llm_response_not_json")
        try:
            payload = json.loads(match.group(0))
        except json.JSONDecodeError as exc:
            raise LlmResponseValidationError("llm_response_not_json") from exc

    if not isinstance(payload, dict):
        raise LlmResponseValidationError("llm_response_must_be_object")
    return payload


def validate_llm_response(payload: dict[str, Any]) -> dict[str, Any]:
    required_fields = {"i", "t", "a", "c", "d", "dt", "cf", "ask"}
    missing = required_fields - payload.keys()
    if missing:
        raise LlmResponseValidationError(f"llm_response_missing_fields:{sorted(missing)}")

    intent_code = str(payload["i"]).upper()
    transaction_type = str(payload["t"]).lower()
    category_code = str(payload["c"]).upper()
    date_code = str(payload["dt"]).lower()

    if intent_code not in COMPACT_INTENT_MAP:
        raise LlmResponseValidationError("llm_response_invalid_intent")
    if transaction_type not in {"income", "expense", "none"}:
        raise LlmResponseValidationError("llm_response_invalid_type")
    if category_code not in CATEGORY_CODE_MAP:
        raise LlmResponseValidationError("llm_response_invalid_category")
    if date_code not in DATE_CODE_MAP:
        raise LlmResponseValidationError("llm_response_invalid_date")
    if not isinstance(payload["ask"], bool):
        raise LlmResponseValidationError("llm_response_invalid_ask")

    try:
        amount = int(payload["a"])
    except (TypeError, ValueError) as exc:
        raise LlmResponseValidationError("llm_response_invalid_amount") from exc
    if amount < 0:
        raise LlmResponseValidationError("llm_response_invalid_amount")

    try:
        confidence = float(payload["cf"])
    except (TypeError, ValueError) as exc:
        raise LlmResponseValidationError("llm_response_invalid_confidence") from exc
    if confidence < 0 or confidence > 1:
        raise LlmResponseValidationError("llm_response_invalid_confidence")

    description = payload["d"]
    if description is None:
        description = ""
    if not isinstance(description, str):
        raise LlmResponseValidationError("llm_response_invalid_description")

    return {
        "i": intent_code,
        "t": transaction_type,
        "a": amount,
        "c": category_code,
        "d": description.strip(),
        "dt": date_code,
        "cf": confidence,
        "ask": payload["ask"],
    }


def expand_llm_response(
    payload: dict[str, Any],
    *,
    source: str,
    today: date | None = None,
) -> dict[str, Any]:
    compact = validate_llm_response(payload)
    current_date = today or date.today()
    intent = COMPACT_INTENT_MAP[compact["i"]]
    amount = Decimal(compact["a"]) if compact["a"] > 0 else None
    transaction_type = compact["t"] if compact["t"] != "none" else None
    transaction_date = _resolve_transaction_date(compact["dt"], current_date)
    confidence = compact["cf"]
    need_confirmation = bool(
        compact["ask"]
        or confidence < 0.85
        or (intent == INTENT_ADD_TRANSACTION and amount is None)
        or (intent == INTENT_ADD_TRANSACTION and transaction_type is None)
    )

    return {
        "intent": intent,
        "type": transaction_type,
        "amount": amount,
        "category": CATEGORY_CODE_MAP[compact["c"]],
        "description": compact["d"] or None,
        "transaction_date": transaction_date,
        "source": source,
        "confidence": confidence,
        "need_confirmation": need_confirmation,
        "reasons": ["llm_fallback"],
        "period": DATE_CODE_MAP[compact["dt"]],
        "metadata": {
            "llm_intent_code": compact["i"],
            "llm_category_code": compact["c"],
            "llm_date_code": compact["dt"],
        },
    }


def _resolve_transaction_date(date_code: str, current_date: date) -> date:
    if date_code == "yesterday":
        return current_date - timedelta(days=1)
    return current_date
