from __future__ import annotations

import re
from datetime import date, timedelta

from app.modules.parser.schemas import DateMatch


DATE_PATTERNS: tuple[tuple[re.Pattern[str], int, str], ...] = (
    (re.compile(r"\b(kemarin|yesterday)\b", re.IGNORECASE), -1, "yesterday"),
    (re.compile(r"\b(hari ini|today)\b", re.IGNORECASE), 0, "today"),
    (re.compile(r"\b(besok|tomorrow)\b", re.IGNORECASE), 1, "tomorrow"),
)
DATE_PERIOD_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bminggu ini\b", re.IGNORECASE), "this_week"),
    (re.compile(r"\bbulan ini\b", re.IGNORECASE), "this_month"),
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


def parse_transaction_date(text: str, current_date: date) -> DateMatch | None:
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

    for pattern, offset, period_code in DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            return DateMatch(
                value=current_date + timedelta(days=offset),
                start=match.start(),
                end=match.end(),
                explicit=False,
                period_code=period_code,
            )

    for pattern, period_code in DATE_PERIOD_PATTERNS:
        match = pattern.search(text)
        if match:
            return DateMatch(
                value=current_date,
                start=match.start(),
                end=match.end(),
                explicit=False,
                period_code=period_code,
            )

    return None


def detect_period(text: str) -> str | None:
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
