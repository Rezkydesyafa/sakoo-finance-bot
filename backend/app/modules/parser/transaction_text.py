import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any


SOURCE_WHATSAPP_TEXT = "whatsapp_text"
CONFIRMATION_THRESHOLD = 0.75

AMOUNT_RE = re.compile(
    r"(?<!\w)(?P<prefix>rp\.?\s*)?"
    r"(?P<number>\d+(?:[.,]\d{3})*(?:[.,]\d+)?)"
    r"\s*(?P<unit>juta|jt|ribu|rb|k)?\b",
    re.IGNORECASE,
)

DATE_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"\b(kemarin|yesterday)\b", re.IGNORECASE), -1),
    (re.compile(r"\b(hari ini|today)\b", re.IGNORECASE), 0),
)

INCOME_KEYWORDS = {
    "bonus",
    "dibayar",
    "freelance",
    "gaji",
    "income",
    "masuk",
    "pendapatan",
    "pemasukan",
    "salary",
    "terima",
    "upah",
}
EXPENSE_KEYWORDS = {
    "bayar",
    "beli",
    "belanja",
    "jajan",
    "keluar",
    "makan",
    "pengeluaran",
}

CATEGORY_KEYWORDS: tuple[tuple[str, str, set[str]], ...] = (
    (
        "Makanan",
        "expense",
        {
            "ayam",
            "bakso",
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
            "ojek",
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
            "lazada",
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
        {"buku", "kelas", "kuliah", "kursus", "pendidikan", "sekolah"},
    ),
    (
        "Gaji",
        "income",
        {"bonus", "freelance", "gaji", "invoice", "pendapatan", "salary", "upah"},
    ),
    ("Tabungan", "income", {"investasi", "nabung", "saving", "tabung", "tabungan"}),
)


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
        }


@dataclass(frozen=True)
class AmountMatch:
    value: Decimal
    start: int
    end: int
    score: float


def parse_transaction_text(text: str, today: date | None = None) -> ParsedTransactionText:
    current_date = today or date.today()
    normalized = _normalize_text(text)
    amount_match = _extract_amount(normalized)
    transaction_type, has_type_keyword = _detect_type(normalized)
    category, category_type, has_category_keyword = _detect_category(normalized)
    transaction_date = _detect_date(normalized, current_date)
    description = _build_description(normalized, amount_match)
    reasons: list[str] = []

    if amount_match is None:
        reasons.append("missing_amount")
    if not has_type_keyword and transaction_type == "expense":
        reasons.append("default_expense_type")
    if category is None:
        reasons.append("category_fallback")
        category = "Gaji" if transaction_type == "income" else "Lainnya"
    elif category_type and category_type != transaction_type:
        transaction_type = category_type

    confidence = _calculate_confidence(
        has_amount=amount_match is not None,
        has_type_keyword=has_type_keyword,
        has_category_keyword=has_category_keyword,
        has_description=bool(description),
        has_date=transaction_date is not None,
    )
    need_confirmation = (
        amount_match is None
        or transaction_type is None
        or confidence < CONFIRMATION_THRESHOLD
    )

    return ParsedTransactionText(
        intent="add_transaction",
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


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _extract_amount(text: str) -> AmountMatch | None:
    matches: list[AmountMatch] = []
    for match in AMOUNT_RE.finditer(text):
        value = _parse_amount_value(
            match.group("number"),
            match.group("unit"),
            has_rupiah_prefix=bool(match.group("prefix")),
        )
        if value is None or value <= 0:
            continue

        score = float(match.start()) / max(len(text), 1)
        if match.group("unit"):
            score += 3
        if match.group("prefix"):
            score += 2
        if value >= Decimal("1000"):
            score += 1
        matches.append(
            AmountMatch(
                value=value,
                start=match.start(),
                end=match.end(),
                score=score,
            )
        )

    return max(matches, key=lambda item: item.score) if matches else None


def _parse_amount_value(
    number: str,
    unit: str | None,
    *,
    has_rupiah_prefix: bool,
) -> Decimal | None:
    unit_normalized = (unit or "").lower()
    try:
        if unit_normalized:
            value = Decimal(_normalize_decimal_number(number))
        elif has_rupiah_prefix or "." in number or "," in number:
            value = Decimal(re.sub(r"[^\d]", "", number))
        else:
            value = Decimal(number)
    except (InvalidOperation, ValueError):
        return None

    if unit_normalized in {"ribu", "rb", "k"}:
        value *= Decimal("1000")
    elif unit_normalized in {"juta", "jt"}:
        value *= Decimal("1000000")

    return value.quantize(Decimal("1"))


def _normalize_decimal_number(number: str) -> str:
    if "." in number and "," in number:
        return number.replace(".", "").replace(",", ".")
    if "," in number:
        return number.replace(",", ".")
    return number


def _detect_type(text: str) -> tuple[str, bool]:
    tokens = _tokenize(text)
    if tokens & INCOME_KEYWORDS:
        return "income", True
    if tokens & EXPENSE_KEYWORDS:
        return "expense", True
    return "expense", False


def _detect_category(text: str) -> tuple[str | None, str | None, bool]:
    tokens = _tokenize(text)
    for category, category_type, keywords in CATEGORY_KEYWORDS:
        if tokens & keywords or any(keyword in text for keyword in keywords if " " in keyword):
            return category, category_type, True
    return None, None, False


def _detect_date(text: str, current_date: date) -> date:
    for pattern, offset in DATE_PATTERNS:
        if pattern.search(text):
            return current_date + timedelta(days=offset)
    return current_date


def _build_description(text: str, amount_match: AmountMatch | None) -> str | None:
    description = text
    if amount_match:
        description = f"{text[:amount_match.start]} {text[amount_match.end:]}"

    for pattern, _offset in DATE_PATTERNS:
        description = pattern.sub(" ", description)

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
