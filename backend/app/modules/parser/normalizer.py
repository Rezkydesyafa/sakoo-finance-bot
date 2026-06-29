from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation


_SPACES_RE = re.compile(r"\s+")
_AMOUNT_NORMALIZATION_RE = re.compile(
    r"(?<![\w/-])(?P<prefix>rp\.?\s*)?"
    r"(?P<number>\d+(?:[.,]\d{3})*(?:[.,]\d+)?)"
    r"\s*(?P<unit>ribu|juta)?\b",
    re.IGNORECASE,
)
_SLANG_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\babis\b", re.IGNORECASE), "habis"),
    (re.compile(r"\bbuat\b", re.IGNORECASE), "untuk"),
    (re.compile(r"\bduit\b", re.IGNORECASE), "uang"),
    (re.compile(r"\bdapet\b", re.IGNORECASE), "dapat"),
    (re.compile(r"\bdpt\b", re.IGNORECASE), "dapat"),
    (re.compile(r"\bnyokap\b", re.IGNORECASE), "ibu"),
    (re.compile(r"\bbokap\b", re.IGNORECASE), "ayah"),
    (re.compile(r"\bngopi\b", re.IGNORECASE), "kopi"),
    (re.compile(r"\bnongki\b", re.IGNORECASE), "nongkrong"),
    (re.compile(r"\bnugas\b", re.IGNORECASE), "tugas"),
    (re.compile(r"\btop\s+up\b", re.IGNORECASE), "topup"),
    (re.compile(r"(?<=\d)\s*rb\b", re.IGNORECASE), " ribu"),
    (re.compile(r"(?<=\d)\s*jt\b", re.IGNORECASE), " juta"),
    (re.compile(r"(?<=\d)\s*k\b", re.IGNORECASE), " ribu"),
)


def normalize_text(text: str | None) -> str:
    normalized = (text or "").strip().lower()
    for pattern, replacement in _SLANG_PATTERNS:
        normalized = pattern.sub(replacement, normalized)

    normalized = _AMOUNT_NORMALIZATION_RE.sub(_normalize_amount_match, normalized)
    normalized = _SPACES_RE.sub(" ", normalized).strip()
    return normalized


def normalize_for_matching(text: str | None) -> str:
    normalized = normalize_text(text)
    normalized = re.sub(r"[^a-zA-Z0-9\u00c0-\u024f\s/-]", " ", normalized)
    return _SPACES_RE.sub(" ", normalized).strip()


def _normalize_amount_match(match: re.Match[str]) -> str:
    prefix = match.group("prefix")
    number = match.group("number")
    unit = match.group("unit")

    should_normalize = bool(prefix or unit or "." in number or "," in number)
    if not should_normalize:
        return match.group(0)

    value = _parse_amount_value(
        number,
        unit,
        has_rupiah_prefix=bool(prefix),
    )
    return str(int(value)) if value is not None and value > 0 else match.group(0)


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

    if unit_normalized == "ribu":
        value *= Decimal("1000")
    elif unit_normalized == "juta":
        value *= Decimal("1000000")

    return value.quantize(Decimal("1"))


def _normalize_decimal_number(number: str) -> str:
    if "." in number and "," in number:
        return number.replace(".", "").replace(",", ".")
    if "," in number:
        return number.replace(",", ".")
    return number
