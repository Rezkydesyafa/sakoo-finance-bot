from __future__ import annotations

import re

from app.modules.parser.amount_parser import extract_amount
from app.modules.parser.date_parser import detect_period
from app.modules.parser.normalizer import normalize_text
from app.modules.parser.schemas import (
    CATEGORY_HINTS,
    EXPENSE_KEYWORDS,
    INCOME_KEYWORDS,
    INCOME_PHRASES,
    INTENT_ADD_TRANSACTION,
    INTENT_CATEGORY_DETAIL,
    INTENT_CREATE_CATEGORY,
    INTENT_DELETE_LAST_TRANSACTION,
    INTENT_EXPORT_PDF,
    INTENT_FINANCE_CHAT,
    INTENT_GET_BALANCE,
    INTENT_GET_REPORT,
    INTENT_HELP,
    INTENT_LINK_ACCOUNT,
    INTENT_LIST_EXPENSE,
    INTENT_LIST_INCOME,
    INTENT_RECENT_TRANSACTIONS,
    INTENT_SORTED_EXPENSE,
    INTENT_UNKNOWN,
    IntentMatch,
)


HELP_KEYWORDS = {"bantuan", "help", "menu", "panduan", "mulai", "start"}
BALANCE_PHRASES = (
    "saldo",
    "saldo saya",
    "sisa saldo",
    "uang tersisa",
    "sisa uang",
)
REPORT_KEYWORDS = {"laporan", "rekap", "ringkasan"}
EXPORT_KEYWORDS = {"download", "ekspor", "export", "pdf", "unduh"}
LIST_EXPENSE_PHRASES = (
    "list pengeluaran",
    "daftar pengeluaran",
    "pengeluaran bulan ini",
    "pengeluaran minggu ini",
    "pengeluaran hari ini",
    "pengeluaran kemarin",
    "pengeluaran terbaru",
    "apa saja pengeluaran",
    "apa aja pengeluaran",
)
LIST_INCOME_PHRASES = (
    "list pemasukan",
    "daftar pemasukan",
    "pemasukan bulan ini",
    "pemasukan minggu ini",
    "pemasukan hari ini",
    "pemasukan kemarin",
    "apa saja pemasukan",
    "apa aja pemasukan",
)
RECENT_TRANSACTION_PHRASES = (
    "riwayat",
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
LINK_ACCOUNT_PHRASES = ("hubungkan", "link akun", "sambungkan")
CREATE_CATEGORY_RE = re.compile(
    r"\b(?:buat(?:kan)?|bikin|tambah(?:kan)?|create)\b.*\bkategori\b"
    r"|\bkategori\b.*\b(?:baru|buat(?:kan)?|bikin|tambah(?:kan)?)\b",
    re.IGNORECASE,
)
FINANCE_EDUCATION_RE = re.compile(
    r"\b(?:"
    r"tips?\s+(?:menabung|hemat|keuangan|investasi|nabung|budgeting|finansial)"
    r"|strategi\s+(?:menabung|keuangan|nabung|finansial|investasi|saving)"
    r"|cara\s+(?:mengatur|mengelola|manage|atur)\s+(?:uang|keuangan|finansial|gaji)"
    r"|cara\s+(?:menabung|nabung|hemat|saving|investasi)"
    r"|(?:penting|manfaat|keuntungan|fungsi|tujuan).*(?:keuangan|menabung|nabung|budgeting|investasi|finansial)"
    r"|(?:keuangan|menabung|nabung|budgeting|investasi|finansial).*(?:penting|manfaat|keuntungan|fungsi|tujuan)"
    r"|apa\s+(?:itu|yang dimaksud)\s+(?:budgeting|investasi|tabungan|reksadana|saham|obligasi|deposito|inflasi|finansial)"
    r"|jelaskan.*(?:keuangan|menabung|nabung|budgeting|investasi|finansial|tabungan|uang)"
    r"|saran\s+(?:keuangan|finansial|investasi|menabung|nabung)"
    r"|(?:tolong|bantu|coba).*(?:strategi|tips?|saran|rencana).*(?:menabung|nabung|keuangan|hemat|investasi)"
    r"|(?:bantu|tolong).*(?:atur|kelola).*(?:uang|keuangan)"
    r"|(?:evaluasi|sehat|ngurangin|kurangi|stop langganan|target nabung|pengen nabung).*(?:uang|keuangan|pengeluaran|jajan|tabungan|nabung|langganan)?"
    r")\b",
    re.IGNORECASE,
)

# Match patterns like "tampilkan 10 pengeluaran", "liat 5 pemasukan", "lihat 20 pengeluaran"
LIST_WITH_LIMIT_RE = re.compile(
    r"\b(?:tampilkan|liat|lihat|tunjukkan|show|kasih liat|kasih lihat)\b"
    r".*?\b(?P<limit>\d+)\s*"
    r"(?P<type>pengeluaran|pemasukan|expense|income)\b",
    re.IGNORECASE,
)

# Also match "10 pengeluaran terakhir", "5 transaksi pengeluaran"
LIST_LIMIT_SUFFIX_RE = re.compile(
    r"\b(?P<limit>\d+)\s*(?P<type>pengeluaran|pemasukan|expense|income)"
    r"\s*(?:terakhir|terbaru|terkini)?\b",
    re.IGNORECASE,
)
ALL_LIST_RE = re.compile(
    r"\b(?:semua|seluruh|full)\b.*\b(?P<type>pengeluaran|pemasukan|expense|income)\b"
    r"|\b(?P<type2>pengeluaran|pemasukan|expense|income)\b.*\b(?:semua|seluruh|full)\b",
    re.IGNORECASE,
)
GENERIC_LIST_RE = re.compile(
    r"\b(?:list|daftar|tampilkan|lihat|liat|kasih\s+lihat|kasih\s+liat|buatkan)\b"
    r".*\b(?P<type>pengeluaran|pemasukan|expense|income)\b"
    r"|\b(?P<type2>pengeluaran|pemasukan|expense|income)\b.*\b(?:apa\s+saja|apa\s+aja|list|daftar)\b",
    re.IGNORECASE,
)

# Match "urutkan pengeluaran terbesar bulan ini", "sortir pengeluaran terbesar"
SORTED_EXPENSE_RE = re.compile(
    r"\b(?:urutkan|sortir|sort|ranking|peringkat|susun)\b"
    r".*\b(?:pengeluaran|pemasukan|expense|income)\b"
    r".*\b(?:terbesar|terkecil|tertinggi|terendah)\b",
    re.IGNORECASE,
)
DATE_SORT_RE = re.compile(
    r"\b(?:urutkan|sortir|sort|susun)\b.*\b(?:pengeluaran|list)\b.*"
    r"\b(?P<order>terlama|terbaru|terkini)\b"
    r"|\b(?:urutkan|sortir|sort|susun)\b.*\b(?P<order2>terlama|terbaru|terkini)\b",
    re.IGNORECASE,
)

# Match category detail queries like "tagihan apa itu", "makanan berapa bulan ini"
CATEGORY_DETAIL_RE = re.compile(
    r"\b(?P<category>makan(?:an)?|kopi|transport(?:asi)?|bensin|tagihan|belanja|"
    r"hiburan|kesehatan|pendidikan|kuliah|kampus|kos|gaji|tabungan)\b"
    r"\s+(?:apa\s+(?:itu|saja|aja)|berapa|rincian|detail|rinci)",
    re.IGNORECASE,
)

COMMAND_INTENTS = {
    "/start": INTENT_HELP,
    "/help": INTENT_HELP,
    "/saldo": INTENT_GET_BALANCE,
    "/laporan": INTENT_GET_REPORT,
    "/export": INTENT_EXPORT_PDF,
    "/pengeluaran": INTENT_LIST_EXPENSE,
    "/pemasukan": INTENT_LIST_INCOME,
    "/riwayat": INTENT_RECENT_TRANSACTIONS,
}


def detect_intent(text: str) -> IntentMatch:
    normalized = normalize_text(text)
    tokens = _tokenize(normalized)
    period = detect_period(normalized)

    command = _extract_command(normalized)
    if command:
        intent = COMMAND_INTENTS.get(command, INTENT_UNKNOWN)
        return IntentMatch(intent=intent, period=period, confidence=1.0)

    if tokens & HELP_KEYWORDS and len(tokens) <= 4:
        return IntentMatch(intent=INTENT_HELP, confidence=1.0)

    # Category create must come BEFORE transaction language check
    # because "buat kategori tugas" contains "tugas" which is a CATEGORY_HINT
    if CREATE_CATEGORY_RE.search(normalized):
        return IntentMatch(intent=INTENT_CREATE_CATEGORY, confidence=0.95)

    if _contains_phrase(normalized, LINK_ACCOUNT_PHRASES):
        return IntentMatch(intent=INTENT_LINK_ACCOUNT, confidence=0.95)
    if _contains_phrase(normalized, DELETE_LAST_PHRASES):
        return IntentMatch(intent=INTENT_DELETE_LAST_TRANSACTION, confidence=1.0)

    # Sorted expense: "urutkan pengeluaran terbesar bulan ini"
    sorted_match = SORTED_EXPENSE_RE.search(normalized)
    if sorted_match:
        sort_order = "desc"
        if re.search(r"\bterkecil|terendah\b", normalized):
            sort_order = "asc"
        return IntentMatch(
            intent=INTENT_SORTED_EXPENSE,
            period=period or "month",
            confidence=1.0,
            sort_order=sort_order,
        )

    date_sort_match = DATE_SORT_RE.search(normalized)
    if date_sort_match:
        order = (date_sort_match.group("order") or date_sort_match.group("order2") or "").lower()
        return IntentMatch(
            intent=INTENT_SORTED_EXPENSE,
            period=period or "month",
            confidence=1.0,
            sort_order="date_asc" if order == "terlama" else "date_desc",
        )

    all_list_match = ALL_LIST_RE.search(normalized)
    if all_list_match:
        txn_type_word = (all_list_match.group("type") or all_list_match.group("type2")).lower()
        intent = INTENT_LIST_INCOME if txn_type_word in {"pemasukan", "income"} else INTENT_LIST_EXPENSE
        return IntentMatch(intent=intent, period=period, confidence=1.0, limit=50)

    # List with explicit limit: "tampilkan 10 pengeluaran", "liat 5 pemasukan"
    limit_match = LIST_WITH_LIMIT_RE.search(normalized)
    if limit_match:
        limit = int(limit_match.group("limit"))
        txn_type_word = limit_match.group("type").lower()
        intent = INTENT_LIST_INCOME if txn_type_word in {"pemasukan", "income"} else INTENT_LIST_EXPENSE
        return IntentMatch(intent=intent, period=period, confidence=1.0, limit=limit)

    # Also check "10 pengeluaran terakhir" pattern (without leading verb)
    limit_suffix_match = LIST_LIMIT_SUFFIX_RE.search(normalized)
    if limit_suffix_match and not _looks_like_transaction_input(normalized):
        limit = int(limit_suffix_match.group("limit"))
        txn_type_word = limit_suffix_match.group("type").lower()
        intent = INTENT_LIST_INCOME if txn_type_word in {"pemasukan", "income"} else INTENT_LIST_EXPENSE
        return IntentMatch(intent=intent, period=period, confidence=1.0, limit=limit)

    generic_list_match = GENERIC_LIST_RE.search(normalized)
    if generic_list_match and not _looks_like_transaction_input(normalized):
        txn_type_word = (generic_list_match.group("type") or generic_list_match.group("type2")).lower()
        intent = INTENT_LIST_INCOME if txn_type_word in {"pemasukan", "income"} else INTENT_LIST_EXPENSE
        return IntentMatch(intent=intent, period=period, confidence=1.0)

    # Category detail: "tagihan apa itu?", "makanan berapa bulan ini"
    category_detail_match = CATEGORY_DETAIL_RE.search(normalized)
    if category_detail_match:
        category_name = _category_name_from_alias(category_detail_match.group("category"))
        return IntentMatch(
            intent=INTENT_CATEGORY_DETAIL,
            period=period or "month",
            confidence=1.0,
            category_filter=category_name,
        )

    # List expense/income phrases
    if _contains_phrase(normalized, LIST_EXPENSE_PHRASES):
        return IntentMatch(intent=INTENT_LIST_EXPENSE, period=period, confidence=1.0)
    if _contains_phrase(normalized, LIST_INCOME_PHRASES):
        return IntentMatch(intent=INTENT_LIST_INCOME, period=period, confidence=1.0)
    if _contains_phrase(normalized, RECENT_TRANSACTION_PHRASES):
        return IntentMatch(intent=INTENT_RECENT_TRANSACTIONS, period=period, confidence=1.0)
    if _contains_phrase(normalized, BALANCE_PHRASES):
        return IntentMatch(intent=INTENT_GET_BALANCE, confidence=1.0)

    # Transaction detection BEFORE report/export keywords
    # to prevent "beli buku laporan 20rb" from matching as get_report
    if _looks_like_transaction_input(normalized):
        return IntentMatch(intent=INTENT_ADD_TRANSACTION, confidence=0.95)

    if (tokens & EXPORT_KEYWORDS) and (tokens & REPORT_KEYWORDS):
        return IntentMatch(intent=INTENT_EXPORT_PDF, period=period, confidence=1.0)
    if tokens & REPORT_KEYWORDS:
        return IntentMatch(intent=INTENT_GET_REPORT, period=period, confidence=1.0)

    if _has_transaction_language(normalized):
        return IntentMatch(intent=INTENT_ADD_TRANSACTION, confidence=0.75)

    if FINANCE_EDUCATION_RE.search(normalized):
        return IntentMatch(intent=INTENT_FINANCE_CHAT, confidence=0.90)

    return IntentMatch(intent=INTENT_UNKNOWN, confidence=0.25)


def _looks_like_transaction_input(text: str) -> bool:
    if extract_amount(text) is None:
        return False
    return _has_transaction_language(text)


def _has_transaction_language(text: str) -> bool:
    tokens = _tokenize(text)
    if tokens & INCOME_KEYWORDS:
        return True
    if tokens & EXPENSE_KEYWORDS:
        return True
    if tokens & CATEGORY_HINTS:
        return True
    return any(phrase in text for phrase in INCOME_PHRASES)


def _extract_command(text: str) -> str | None:
    match = re.match(r"^(/[a-zA-Z]+)\b", text)
    return match.group(1).lower() if match else None


def _contains_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z\u00c0-\u024f]+", text.lower()))


def _category_name_from_alias(alias: str) -> str:
    normalized = alias.lower()
    if normalized in {"makan", "makanan", "kopi"}:
        return "Makanan"
    if normalized in {"transport", "transportasi", "bensin"}:
        return "Transportasi"
    if normalized in {"kos", "tagihan"}:
        return "Tagihan"
    if normalized == "belanja":
        return "Belanja"
    if normalized == "hiburan":
        return "Hiburan"
    if normalized == "kesehatan":
        return "Kesehatan"
    if normalized in {"pendidikan", "kuliah", "kampus"}:
        return "Pendidikan"
    if normalized == "gaji":
        return "Gaji"
    if normalized == "tabungan":
        return "Tabungan"
    return normalized.title()
