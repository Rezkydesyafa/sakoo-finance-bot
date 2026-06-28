import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


TOTAL_CONFIDENCE_THRESHOLD = 0.75
CONFIDENCE_QUANT = Decimal("0.0001")
AMOUNT_QUANT = Decimal("0.01")

TOTAL_KEYWORDS: tuple[tuple[str, re.Pattern[str], int], ...] = (
    ("grand_total", re.compile(r"\bgrand\s+total\b", re.IGNORECASE), 5),
    (
        "total_bayar",
        re.compile(
            r"\btotal\s+(?:bayar|belanja|pembayaran|purchase|amount)\b",
            re.IGNORECASE,
        ),
        5,
    ),
    ("total", re.compile(r"\btotal\b", re.IGNORECASE), 4),
)
IGNORED_TOTAL_LINE_RE = re.compile(
    r"\b(?:sub\s*total|subtotal|total\s+item|item\s+total|qty|quantity|jumlah\s+item)\b",
    re.IGNORECASE,
)
AMOUNT_RE = re.compile(
    r"(?<![\d/.-])(?:rp|idr)?\.?\s*"
    r"(?P<number>\d{1,3}(?:[.,\s]\d{3})+(?:[.,]\d{2})?|\d{4,})"
    r"(?![\d/])",
    re.IGNORECASE,
)
DATE_YMD_RE = re.compile(
    r"\b(?P<year>\d{4})[/-](?P<month>0?[1-9]|1[0-2])[/-](?P<day>[0-3]?\d)\b"
)
DATE_DMY_RE = re.compile(
    r"\b(?P<day>[0-3]?\d)[/-](?P<month>0?[1-9]|1[0-2])"
    r"(?:[/-](?P<year>\d{2,4}))?\b"
)
DATE_MONTH_NAME_RE = re.compile(
    r"\b(?P<day>[0-3]?\d)\s+"
    r"(?P<month>jan(?:uari)?|feb(?:ruari)?|mar(?:et)?|apr(?:il)?|mei|"
    r"jun(?:i)?|jul(?:i)?|agu(?:stus)?|sep(?:tember)?|okt(?:ober)?|"
    r"nov(?:ember)?|des(?:ember)?|jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|"
    r"apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|"
    r"oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"(?:\s+(?P<year>\d{2,4}))?\b",
    re.IGNORECASE,
)
MERCHANT_NOISE_RE = re.compile(
    r"\b(?:alamat|cashier|date|faktur|jalan|jl\.?|kasir|npwp|nota|no\.?|"
    r"receipt|struk|telp|tanggal|tax|time|waktu)\b",
    re.IGNORECASE,
)
LETTER_RE = re.compile(r"[A-Za-z]")

MONTH_ALIASES = {
    "jan": 1,
    "januari": 1,
    "january": 1,
    "feb": 2,
    "februari": 2,
    "february": 2,
    "mar": 3,
    "maret": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "mei": 5,
    "may": 5,
    "jun": 6,
    "juni": 6,
    "june": 6,
    "jul": 7,
    "juli": 7,
    "july": 7,
    "agu": 8,
    "agustus": 8,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "okt": 10,
    "oktober": 10,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "des": 12,
    "desember": 12,
    "dec": 12,
    "december": 12,
}


@dataclass(frozen=True)
class ReceiptParseResult:
    total_amount: Decimal | None
    merchant_name: str | None
    receipt_date: date | None
    confidence: Decimal
    status: str
    need_confirmation: bool
    reasons: list[str]


@dataclass(frozen=True)
class TotalCandidate:
    amount: Decimal
    keyword: str
    priority: int
    line_index: int


def parse_receipt_text(text: str, current_year: int | None = None) -> ReceiptParseResult:
    lines = _normalize_lines(text)
    merchant_name = _extract_merchant(lines)
    receipt_date = _extract_date(lines, current_year=current_year)
    total_candidate, ambiguous_total = _extract_total(lines)
    reasons: list[str] = []

    if total_candidate is None:
        reasons.append("missing_total_keyword")
        if _extract_all_amounts(lines):
            reasons.append("ambiguous_amounts_without_total_keyword")
        confidence = _calculate_confidence(
            has_total=False,
            has_merchant=merchant_name is not None,
            has_date=receipt_date is not None,
            ambiguous=False,
        )
        return ReceiptParseResult(
            total_amount=None,
            merchant_name=merchant_name,
            receipt_date=receipt_date,
            confidence=confidence,
            status="manual_input_required",
            need_confirmation=True,
            reasons=reasons,
        )

    if ambiguous_total:
        reasons.append("multiple_total_candidates")

    confidence = _calculate_confidence(
        has_total=True,
        has_merchant=merchant_name is not None,
        has_date=receipt_date is not None,
        ambiguous=ambiguous_total,
    )
    need_confirmation = ambiguous_total or confidence < Decimal(str(TOTAL_CONFIDENCE_THRESHOLD))
    return ReceiptParseResult(
        total_amount=total_candidate.amount,
        merchant_name=merchant_name,
        receipt_date=receipt_date,
        confidence=confidence,
        status="needs_confirmation" if need_confirmation else "processed",
        need_confirmation=need_confirmation,
        reasons=reasons,
    )


def _normalize_lines(text: str) -> list[str]:
    return [
        re.sub(r"\s+", " ", line).strip()
        for line in text.splitlines()
        if re.sub(r"\s+", " ", line).strip()
    ]


def _extract_total(lines: list[str]) -> tuple[TotalCandidate | None, bool]:
    candidates: list[TotalCandidate] = []
    for line_index, line in enumerate(lines):
        if IGNORED_TOTAL_LINE_RE.search(line):
            continue

        for keyword, pattern, priority in TOTAL_KEYWORDS:
            keyword_match = pattern.search(line)
            if not keyword_match:
                continue

            amount = _first_amount_after_keyword(line, keyword_match.end())
            if amount is None:
                amount = _first_amount_from_next_lines(lines, line_index)
            if amount is not None:
                candidates.append(
                    TotalCandidate(
                        amount=amount,
                        keyword=keyword,
                        priority=priority,
                        line_index=line_index,
                    )
                )
            break

    if not candidates:
        return None, False

    max_priority = max(candidate.priority for candidate in candidates)
    strongest = [
        candidate for candidate in candidates if candidate.priority == max_priority
    ]
    distinct_amounts = {candidate.amount for candidate in strongest}
    selected = strongest[-1]
    return selected, len(distinct_amounts) > 1


def _first_amount_after_keyword(line: str, keyword_end: int) -> Decimal | None:
    for match in AMOUNT_RE.finditer(line):
        if match.start() >= keyword_end:
            return _parse_amount(match.group("number"))
    return None


def _first_amount_from_next_lines(lines: list[str], line_index: int) -> Decimal | None:
    for next_line in lines[line_index + 1 : line_index + 3]:
        amounts = _extract_amounts_from_line(next_line)
        if amounts:
            return amounts[0]
    return None


def _extract_all_amounts(lines: list[str]) -> list[Decimal]:
    amounts: list[Decimal] = []
    for line in lines:
        amounts.extend(_extract_amounts_from_line(line))
    return amounts


def _extract_amounts_from_line(line: str) -> list[Decimal]:
    amounts: list[Decimal] = []
    for match in AMOUNT_RE.finditer(line):
        amount = _parse_amount(match.group("number"))
        if amount is not None:
            amounts.append(amount)
    return amounts


def _parse_amount(raw_number: str) -> Decimal | None:
    cleaned = re.sub(r"\s+", "", raw_number)
    if not cleaned:
        return None

    decimal_number = _normalize_amount_number(cleaned)
    try:
        amount = Decimal(decimal_number).quantize(AMOUNT_QUANT, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return None

    if amount < Decimal("100"):
        return None
    return amount


def _normalize_amount_number(value: str) -> str:
    if "." in value and "," in value:
        last_dot = value.rfind(".")
        last_comma = value.rfind(",")
        decimal_separator = "." if last_dot > last_comma else ","
        thousands_separator = "," if decimal_separator == "." else "."
        return value.replace(thousands_separator, "").replace(decimal_separator, ".")

    separator = "." if "." in value else "," if "," in value else None
    if separator is None:
        return value

    parts = value.split(separator)
    if len(parts) > 2:
        return "".join(parts)

    whole, fraction = parts
    if len(fraction) == 3:
        return whole + fraction
    if len(fraction) == 2 and len(whole) > 3:
        return f"{whole}.{fraction}"
    return whole + fraction


def _extract_merchant(lines: list[str]) -> str | None:
    for line in lines[:8]:
        candidate = line.strip(" -:|")
        if len(candidate) < 3 or not LETTER_RE.search(candidate):
            continue
        if AMOUNT_RE.search(candidate) or _extract_date_from_line(candidate, None):
            continue
        if MERCHANT_NOISE_RE.search(candidate):
            continue
        if any(pattern.search(candidate) for _keyword, pattern, _priority in TOTAL_KEYWORDS):
            continue
        return candidate[:160]
    return None


def _extract_date(lines: list[str], current_year: int | None) -> date | None:
    for line in lines:
        parsed_date = _extract_date_from_line(line, current_year)
        if parsed_date:
            return parsed_date
    return None


def _extract_date_from_line(line: str, current_year: int | None) -> date | None:
    ymd_match = DATE_YMD_RE.search(line)
    if ymd_match:
        return _build_date(
            day=int(ymd_match.group("day")),
            month=int(ymd_match.group("month")),
            year=int(ymd_match.group("year")),
        )

    dmy_match = DATE_DMY_RE.search(line)
    if dmy_match:
        return _build_date(
            day=int(dmy_match.group("day")),
            month=int(dmy_match.group("month")),
            year=_parse_year(dmy_match.group("year"), current_year),
        )

    month_name_match = DATE_MONTH_NAME_RE.search(line)
    if month_name_match:
        month_key = month_name_match.group("month").lower()
        return _build_date(
            day=int(month_name_match.group("day")),
            month=MONTH_ALIASES[month_key],
            year=_parse_year(month_name_match.group("year"), current_year),
        )

    return None


def _parse_year(raw_year: str | None, current_year: int | None) -> int:
    if raw_year is None:
        return current_year or date.today().year
    year = int(raw_year)
    if year < 100:
        return 2000 + year
    return year


def _build_date(*, day: int, month: int, year: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _calculate_confidence(
    *,
    has_total: bool,
    has_merchant: bool,
    has_date: bool,
    ambiguous: bool,
) -> Decimal:
    confidence = Decimal("0")
    if has_total:
        confidence += Decimal("0.65")
    if has_merchant:
        confidence += Decimal("0.15")
    if has_date:
        confidence += Decimal("0.15")
    if has_total and not ambiguous:
        confidence += Decimal("0.05")
    if ambiguous:
        confidence -= Decimal("0.20")

    confidence = max(Decimal("0"), min(confidence, Decimal("1")))
    return confidence.quantize(CONFIDENCE_QUANT, rounding=ROUND_HALF_UP)
