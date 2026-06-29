from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.modules.parser.schemas import AmountMatch


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


def extract_amount(text: str) -> AmountMatch | None:
    matches: list[AmountMatch] = []
    for match in AMOUNT_RE.finditer(text):
        value = parse_amount_value(
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


def parse_amount(text: str) -> Decimal | None:
    match = extract_amount(text)
    return match.value if match else None


def parse_amount_value(
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


def _normalize_decimal_number(number: str) -> str:
    if "." in number and "," in number:
        return number.replace(".", "").replace(",", ".")
    if "," in number:
        return number.replace(",", ".")
    return number
