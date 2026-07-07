from __future__ import annotations

import re
from datetime import date

from app.modules.parser.amount_parser import extract_amount
from app.modules.parser.date_parser import DATE_PATTERNS, parse_transaction_date
from app.modules.parser.intent_router import detect_intent
from app.modules.parser.normalizer import normalize_text
from app.modules.parser.schemas import (
    CONFIRMATION_THRESHOLD,
    EXPENSE_KEYWORDS,
    INCOME_KEYWORDS,
    INCOME_PHRASES,
    INTENT_ADD_TRANSACTION,
    SOURCE_WHATSAPP_TEXT,
    AmountMatch,
    DateMatch,
    ParsedTransactionText,
)

CATEGORY_KEYWORDS: tuple[tuple[str, str, set[str]], ...] = (
    (
        "Makanan",
        "expense",
        {
            "ayam",
            "bakso",
            "cafe",
            "geprek",
            "gofood",
            "grabfood",
            "jajan",
            "kopi",
            "makan",
            "makanan",
            "minum",
            "nasi",
            "resto",
            "sarapan",
            "seblak",
            "teh",
            "warung",
        },
    ),
    (
        "Transportasi",
        "expense",
        {
            "angkot",
            "bbm",
            "bensin",
            "bus",
            "gojek",
            "grab",
            "kereta",
            "maxim",
            "mrt",
            "ojek",
            "ojol",
            "parkir",
            "taksi",
            "tol",
            "transport",
        },
    ),
    (
        "Tagihan",
        "expense",
        {
            "air",
            "cicilan",
            "internet",
            "kos",
            "kontrakan",
            "kuota",
            "listrik",
            "paket",
            "pdam",
            "pulsa",
            "sewa",
            "tagihan",
            "wifi",
        },
    ),
    (
        "Belanja",
        "expense",
        {
            "barang",
            "baju",
            "belanja",
            "checkout",
            "dana",
            "gopay",
            "lazada",
            "ovo",
            "produk",
            "sepatu",
            "shopee",
            "supermarket",
            "tokopedia",
        },
    ),
    (
        "Hiburan",
        "expense",
        {"bioskop", "game", "hiburan", "liburan", "netflix", "nonton", "spotify"},
    ),
    (
        "Kesehatan",
        "expense",
        {"dokter", "kesehatan", "klinik", "obat", "rumah sakit", "rs", "vitamin"},
    ),
    (
        "Pendidikan",
        "expense",
        {
            "buku",
            "fotokopi",
            "jurnal",
            "kampus",
            "kelas",
            "kuliah",
            "kursus",
            "makalah",
            "pendidikan",
            "praktikum",
            "print",
            "sekolah",
            "skripsi",
            "tugas",
            "ukt",
        },
    ),
    (
        "Gaji",
        "income",
        {"bonus", "freelance", "gaji", "gajian", "invoice", "pendapatan", "salary", "upah"},
    ),
    ("Uang Saku", "income", {"dikasih", "mama", "temen", "uang saku", "uang jajan"}),
    ("Tabungan", "income", {"cashback", "investasi", "nabung", "refund", "saving", "tabung", "tabungan"}),
)


def parse_transaction_text(text: str, today: date | None = None) -> ParsedTransactionText:
    current_date = today or date.today()
    normalized = normalize_text(text)
    intent_match = detect_intent(normalized)
    if intent_match.intent != INTENT_ADD_TRANSACTION:
        return ParsedTransactionText(
            intent=intent_match.intent,
            type=None,
            amount=None,
            category=None,
            description=normalized or None,
            transaction_date=current_date,
            source=SOURCE_WHATSAPP_TEXT,
            confidence=intent_match.confidence,
            need_confirmation=False,
            reasons=[],
            period=intent_match.period,
            limit=intent_match.limit,
            sort_order=intent_match.sort_order,
            category_filter=intent_match.category_filter,
        )

    amount_match = extract_amount(normalized)
    transaction_type, has_type_keyword = _detect_type(normalized)
    category, category_type, has_category_keyword = _detect_category(normalized)
    date_match = parse_transaction_date(normalized, current_date)
    transaction_date = date_match.value if date_match else current_date
    description = _build_description(normalized, amount_match, date_match)
    reasons: list[str] = []

    if amount_match is None:
        reasons.append("missing_amount")
    if not has_type_keyword and transaction_type == "expense":
        reasons.append("default_expense_type")
    if category is None:
        reasons.append("category_fallback")
        category = "Lainnya"
    elif category_type and category_type != transaction_type:
        transaction_type = category_type

    confidence = _calculate_confidence(
        has_amount=amount_match is not None,
        has_type_keyword=has_type_keyword,
        has_category_keyword=has_category_keyword,
        has_description=bool(description),
        has_date=date_match is not None,
    )
    need_confirmation = (
        amount_match is None
        or transaction_type is None
        or confidence < CONFIRMATION_THRESHOLD
    )

    return ParsedTransactionText(
        intent=INTENT_ADD_TRANSACTION,
        type=transaction_type,
        amount=amount_match.value if amount_match else None,
        category=category,
        description=description,
        transaction_date=transaction_date,
        source=SOURCE_WHATSAPP_TEXT,
        confidence=confidence,
        need_confirmation=need_confirmation,
        reasons=reasons,
    )


def _detect_type(text: str) -> tuple[str, bool]:
    tokens = _tokenize(text)
    if any(phrase in text for phrase in INCOME_PHRASES):
        return "income", True
    if tokens & INCOME_KEYWORDS:
        return "income", True
    if tokens & EXPENSE_KEYWORDS:
        return "expense", True
    return "expense", False


def _detect_category(text: str) -> tuple[str | None, str | None, bool]:
    if "uang saku" in text or "uang jajan" in text:
        return "Uang Saku", "income", True

    tokens = _tokenize(text)
    if tokens & {"refund", "cashback"}:
        return "Tabungan", "income", True
    for category, category_type, keywords in CATEGORY_KEYWORDS:
        if tokens & keywords or any(keyword in text for keyword in keywords if " " in keyword):
            return category, category_type, True
    return None, None, False


def _build_description(
    text: str,
    amount_match: AmountMatch | None,
    date_match: DateMatch | None,
) -> str | None:
    description = text
    spans = [
        (match.start, match.end)
        for match in (amount_match, date_match)
        if match is not None
    ]
    for start, end in sorted(spans, reverse=True):
        description = f"{description[:start]} {description[end:]}"

    for pattern, _offset, _period_code in DATE_PATTERNS:
        description = pattern.sub(" ", description)

    description = re.sub(r"\b(minggu ini|bulan ini)\b", " ", description)
    description = re.sub(r"\s+", " ", description).strip(" -,.")
    return description or None


def _calculate_confidence(
    *,
    has_amount: bool,
    has_type_keyword: bool,
    has_category_keyword: bool,
    has_description: bool,
    has_date: bool,
) -> float:
    confidence = 0.0
    if has_amount:
        confidence += 0.4
    if has_type_keyword:
        confidence += 0.2
    if has_category_keyword:
        confidence += 0.2
    if has_description:
        confidence += 0.1
    if has_date:
        confidence += 0.1
    return min(confidence, 1.0)


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z\u00c0-\u024f]+", text.lower()))
