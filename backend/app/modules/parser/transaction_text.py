import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any


SOURCE_WHATSAPP_TEXT = "whatsapp_text"
CONFIRMATION_THRESHOLD = 0.85
INTENT_ADD_TRANSACTION = "add_transaction"
INTENT_GET_REPORT = "get_report"
INTENT_EXPORT_PDF = "export_pdf"
INTENT_RECENT_TRANSACTIONS = "recent_transactions"
INTENT_DELETE_LAST_TRANSACTION = "delete_last_transaction"
INTENT_HELP = "help"

AMOUNT_RE = re.compile(
    r"(?<!\w)(?P<prefix>rp\.?\s*)?"
    r"(?P<number>\d+(?:[.,]\d{3})*(?:[.,]\d+)?)"
    r"\s*(?P<unit>juta|jt|ribu|rb|k)?\b",
    re.IGNORECASE,
)
AMOUNT_WORDS = {
    "nol": 0,
    "satu": 1,
    "se": 1,
    "dua": 2,
    "tiga": 3,
    "empat": 4,
    "lima": 5,
    "enam": 6,
    "tujuh": 7,
    "delapan": 8,
    "sembilan": 9,
    "sepuluh": 10,
    "sebelas": 11,
}
AMOUNT_WORD_UNITS = {"ribu": 1_000, "juta": 1_000_000}

DATE_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"\b(kemarin|yesterday)\b", re.IGNORECASE), -1),
    (re.compile(r"\b(hari ini|today)\b", re.IGNORECASE), 0),
)
DATE_NUMERIC_RE = re.compile(
    r"\b(?:tanggal\s+)?(?P<day>[0-3]?\d)[/-](?P<month>0?\d|1[0-2])"
    r"(?:[/-](?P<year>\d{2,4}))?\b",
    re.IGNORECASE,
)
DATE_MONTH_NAME_RE = re.compile(
    r"\b(?:tanggal\s+)?(?P<day>[0-3]?\d)\s+"
    r"(?P<month>jan(?:uari)?|feb(?:ruari)?|mar(?:et)?|apr(?:il)?|mei|"
    r"jun(?:i)?|jul(?:i)?|agu(?:stus)?|sep(?:tember)?|okt(?:ober)?|"
    r"nov(?:ember)?|des(?:ember)?)"
    r"(?:\s+(?P<year>\d{2,4}))?\b",
    re.IGNORECASE,
)
MONTH_ALIASES = {
    "jan": 1,
    "januari": 1,
    "feb": 2,
    "februari": 2,
    "mar": 3,
    "maret": 3,
    "apr": 4,
    "april": 4,
    "mei": 5,
    "jun": 6,
    "juni": 6,
    "jul": 7,
    "juli": 7,
    "agu": 8,
    "agustus": 8,
    "sep": 9,
    "september": 9,
    "okt": 10,
    "oktober": 10,
    "nov": 11,
    "november": 11,
    "des": 12,
    "desember": 12,
}

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
    "biaya",
    "jajan",
    "keluar",
    "makan",
    "pengeluaran",
    "topup",
}
HELP_KEYWORDS = {"bantuan", "help", "menu", "panduan"}
REPORT_KEYWORDS = {"laporan", "rekap", "ringkasan"}
EXPORT_KEYWORDS = {"download", "ekspor", "export", "pdf", "unduh"}
RECENT_TRANSACTION_PHRASES = (
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


@dataclass(frozen=True)
class IntentMatch:
    intent: str
    period: str | None = None
    confidence: float = 1.0


def parse_transaction_text(text: str, today: date | None = None) -> ParsedTransactionText:
    current_date = today or date.today()
    normalized = _normalize_text(text)
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
        )

    amount_match = _extract_amount(normalized)
    transaction_type, has_type_keyword = _detect_type(normalized)
    category, category_type, has_category_keyword = _detect_category(normalized)
    date_match = _detect_date(normalized, current_date)
    transaction_date = date_match.value if date_match else current_date
    description = _build_description(normalized, amount_match, date_match)
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
        has_date=date_match is not None,
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


def detect_intent(text: str) -> IntentMatch:
    normalized = _normalize_text(text)
    tokens = _tokenize(normalized)

    if _looks_like_transaction_input(normalized):
        return IntentMatch(intent=INTENT_ADD_TRANSACTION)
    if tokens & HELP_KEYWORDS and len(tokens) <= 3:
        return IntentMatch(intent=INTENT_HELP)

    period = _detect_period(normalized)
    if _contains_phrase(normalized, DELETE_LAST_PHRASES):
        return IntentMatch(intent=INTENT_DELETE_LAST_TRANSACTION)
    if (tokens & EXPORT_KEYWORDS) and (tokens & REPORT_KEYWORDS):
        return IntentMatch(intent=INTENT_EXPORT_PDF, period=period)
    if _contains_phrase(normalized, RECENT_TRANSACTION_PHRASES):
        return IntentMatch(intent=INTENT_RECENT_TRANSACTIONS)
    if tokens & REPORT_KEYWORDS:
        return IntentMatch(intent=INTENT_GET_REPORT, period=period)

    return IntentMatch(intent=INTENT_ADD_TRANSACTION)


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

    matches.extend(_extract_word_amounts(text))
    return max(matches, key=lambda item: item.score) if matches else None


def _extract_word_amounts(text: str) -> list[AmountMatch]:
    tokens = list(re.finditer(r"[a-zA-Z\u00c0-\u024f]+", text.lower()))
    matches: list[AmountMatch] = []
    index = 0
    while index < len(tokens):
        parsed = _parse_word_amount_from(tokens, index)
        if parsed is None:
            index += 1
            continue

        value, end_index = parsed
        start = tokens[index].start()
        end = tokens[end_index - 1].end()
        score = float(start) / max(len(text), 1) + 3
        if value >= Decimal("1000"):
            score += 1
        matches.append(AmountMatch(value=value, start=start, end=end, score=score))
        index = end_index

    return matches


def _parse_word_amount_from(
    tokens: list[re.Match[str]],
    start_index: int,
) -> tuple[Decimal, int] | None:
    total = 0
    current = 0
    consumed_value_word = False
    index = start_index

    while index < len(tokens):
        word = tokens[index].group(0)
        if word in AMOUNT_WORDS:
            current += AMOUNT_WORDS[word]
            consumed_value_word = True
            index += 1
            continue

        if word == "belas" and consumed_value_word and 1 <= current <= 9:
            current += 10
            index += 1
            continue

        if word == "puluh" and consumed_value_word and 1 <= current <= 9:
            current *= 10
            index += 1
            continue

        if word == "ratus" and consumed_value_word and 1 <= current <= 9:
            current *= 100
            index += 1
            continue

        multiplier = AMOUNT_WORD_UNITS.get(word)
        if multiplier is None:
            break

        if not consumed_value_word:
            return None
        total += (current or 1) * multiplier
        index += 1
        return Decimal(total).quantize(Decimal("1")), index

    return None


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


def _detect_date(text: str, current_date: date) -> DateMatch | None:
    numeric_match = DATE_NUMERIC_RE.search(text)
    if numeric_match:
        parsed_date = _build_date(
            day=int(numeric_match.group("day")),
            month=int(numeric_match.group("month")),
            year=_parse_year(numeric_match.group("year"), current_date.year),
        )
        if parsed_date:
            return DateMatch(
                value=parsed_date,
                start=numeric_match.start(),
                end=numeric_match.end(),
                explicit=True,
            )

    month_name_match = DATE_MONTH_NAME_RE.search(text)
    if month_name_match:
        month = MONTH_ALIASES[month_name_match.group("month").lower()]
        parsed_date = _build_date(
            day=int(month_name_match.group("day")),
            month=month,
            year=_parse_year(month_name_match.group("year"), current_date.year),
        )
        if parsed_date:
            return DateMatch(
                value=parsed_date,
                start=month_name_match.start(),
                end=month_name_match.end(),
                explicit=True,
            )

    for pattern, offset in DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            return DateMatch(
                value=current_date + timedelta(days=offset),
                start=match.start(),
                end=match.end(),
                explicit=False,
            )
    return None


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


def _looks_like_transaction_input(text: str) -> bool:
    amount_match = _extract_amount(text)
    if amount_match is None:
        return False
    _transaction_type, has_type_keyword = _detect_type(text)
    _category, _category_type, has_category_keyword = _detect_category(text)
    return has_type_keyword or has_category_keyword


def _contains_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _detect_period(text: str) -> str | None:
    if "bulan ini" in text:
        return "month"
    if "minggu ini" in text:
        return "week"
    if "hari ini" in text:
        return "day"
    if "kemarin" in text:
        return "yesterday"
    return None


def _parse_year(raw_year: str | None, default_year: int) -> int:
    if raw_year is None:
        return default_year
    year = int(raw_year)
    if year < 100:
        return 2000 + year
    return year


def _build_date(*, day: int, month: int, year: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
