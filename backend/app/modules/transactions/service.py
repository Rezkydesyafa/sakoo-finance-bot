import re
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Category, Transaction
from app.modules.bot.conversation_state import (
    CANCELLED_TRANSACTION_STATUS,
    CONFIRMED_TRANSACTION_STATUS,
    clone_parsed_message,
    get_pending_transaction,
    mark_pending_status,
    store_pending_transaction,
    update_pending_transaction,
)
from app.modules.bot.response_templates import (
    format_cancelled_response,
    format_confirmation_request,
    format_help_response,
    format_no_pending_response,
    format_rupiah,
    format_saved_transaction as format_saved_transaction_template,
    format_unknown_response,
)
from app.modules.bot.service import handle_bot_text_message
from app.modules.parser.amount_parser import parse_amount
from app.modules.parser.date_parser import parse_transaction_date
from app.modules.parser.normalizer import normalize_text
from app.modules.parser.service import ParsedMessage
from app.modules.parser.transaction_text import (
    INTENT_ADD_TRANSACTION,
    INTENT_DELETE_LAST_TRANSACTION,
    INTENT_EXPORT_PDF,
    INTENT_GET_BALANCE,
    INTENT_GET_REPORT,
    INTENT_HELP,
    INTENT_LINK_ACCOUNT,
    INTENT_LIST_EXPENSE,
    INTENT_LIST_INCOME,
    INTENT_RECENT_TRANSACTIONS,
    INTENT_UNKNOWN,
)
from app.modules.transactions.repository import (
    calculate_balance,
    count_user_category_transactions,
    find_category,
    list_transactions,
    sum_category_expense,
    sum_transactions,
    top_expense_category,
)


YES_CONFIRMATION_RE = re.compile(
    r"^\s*(?:ya|iya|y|yes|ok|oke|benar|setuju|simpan|gas|lanjut)\s*$",
    re.IGNORECASE,
)
CANCEL_RE = re.compile(r"^\s*(?:batal|cancel|ga jadi|gajadi|jangan|hapus)\s*$", re.IGNORECASE)
EDIT_RE = re.compile(r"^\s*(?:edit|ubah|ganti|koreksi|revisi|bukan)\b", re.IGNORECASE)
THANKS_RE = re.compile(r"^\s*(?:makasih|terima kasih|thanks|thx|tengkyu)\s*[.!]*\s*$", re.IGNORECASE)
ACK_RE = re.compile(r"^\s*(?:oke|ok|sip|siap|noted)\s*[.!]*\s*$", re.IGNORECASE)
SPENDING_CHECK_RE = re.compile(r"\b(?:boros|hemat|pengeluaran.*hari ini|hari ini.*keluar)\b", re.IGNORECASE)
TOP_EXPENSE_RE = re.compile(r"\b(?:pengeluaran terbesar|paling gede|terbesar apa|top pengeluaran)\b", re.IGNORECASE)
CATEGORY_SUMMARY_RE = re.compile(
    r"\b(?P<category>makan(?:an)?|kopi|transport|bensin|tagihan|belanja|hiburan|kesehatan|pendidikan|kos)\b.*\b(?:berapa|total|bulan ini|minggu ini|hari ini)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class TextTransactionResult:
    status: str
    reply_text: str
    parse_result: ParsedMessage
    transaction_id: int | None = None
    error_message: str | None = None

    def to_log_payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["parse_result"] = self.parse_result.to_log_payload()
        return payload


def handle_whatsapp_text_transaction(
    *,
    db: Session,
    user_id: int,
    text: str,
) -> TextTransactionResult:
    return handle_text_transaction(
        db=db,
        user_id=user_id,
        text=text,
        source="whatsapp_text",
    )


def handle_telegram_text_transaction(
    *,
    db: Session,
    user_id: int,
    text: str,
    forced_transaction_type: str | None = None,
) -> TextTransactionResult:
    return handle_text_transaction(
        db=db,
        user_id=user_id,
        text=text,
        source="telegram_text",
        forced_transaction_type=forced_transaction_type,
    )


def handle_text_transaction(
    *,
    db: Session,
    user_id: int,
    text: str,
    source: str,
    forced_transaction_type: str | None = None,
) -> TextTransactionResult:
    pending_result = _handle_pending_transaction_reply(
        db=db,
        user_id=user_id,
        text=text,
        source=source,
    )
    if pending_result is not None:
        return pending_result

    lightweight_result = _handle_lightweight_message(
        db=db,
        user_id=user_id,
        text=text,
        source=source,
    )
    if lightweight_result is not None:
        return lightweight_result

    parse_result, fallback_error = handle_bot_text_message(
        db=db,
        user_id=user_id,
        text=text,
        source=source,
    )
    if forced_transaction_type in {"expense", "income"}:
        parse_result = _apply_forced_transaction_type(
            parse_result,
            transaction_type=forced_transaction_type,
        )
    if parse_result.intent != INTENT_ADD_TRANSACTION:
        return TextTransactionResult(
            status=parse_result.intent,
            reply_text=_format_command_response(db, user_id, parse_result),
            parse_result=parse_result,
            error_message=fallback_error,
        )

    if parse_result.need_confirmation:
        store_pending_transaction(
            db,
            user_id=user_id,
            platform=_platform_from_source(source),
            raw_message=text,
            parse_result=parse_result,
        )
        return TextTransactionResult(
            status="needs_confirmation",
            reply_text=_format_confirmation_request(parse_result),
            parse_result=parse_result,
            error_message=fallback_error or "low_confidence_parser",
        )

    return _save_transaction_from_parse_result(
        db=db,
        user_id=user_id,
        parse_result=parse_result,
    )


def _save_transaction_from_parse_result(
    *,
    db: Session,
    user_id: int,
    parse_result: ParsedMessage,
    pending_log: Any | None = None,
) -> TextTransactionResult:
    if parse_result.amount is None or parse_result.type is None:
        return TextTransactionResult(
            status="needs_confirmation",
            reply_text=_format_confirmation_request(parse_result),
            parse_result=parse_result,
            error_message="incomplete_pending_transaction",
        )

    category = find_category(
        db=db,
        category_name=parse_result.category,
        transaction_type=parse_result.type,
    )
    transaction = Transaction(
        user_id=user_id,
        type=parse_result.type,
        amount=parse_result.amount,
        category_id=category.id if category else None,
        description=parse_result.description,
        transaction_date=parse_result.transaction_date or date.today(),
        source=parse_result.source,
    )
    db.add(transaction)
    db.flush()
    if pending_log is not None:
        mark_pending_status(
            db,
            pending_log=pending_log,
            status=CONFIRMED_TRANSACTION_STATUS,
        )

    return TextTransactionResult(
        status="saved",
        reply_text=_format_saved_transaction(db, user_id, transaction, category),
        parse_result=parse_result,
        transaction_id=transaction.id,
    )


def _handle_pending_transaction_reply(
    *,
    db: Session,
    user_id: int,
    text: str,
    source: str,
) -> TextTransactionResult | None:
    pending = get_pending_transaction(db, user_id=user_id)
    normalized = normalize_text(text)

    if pending is None:
        if CANCEL_RE.match(normalized):
            return TextTransactionResult(
                status="no_pending_confirmation",
                reply_text=format_no_pending_response(),
                parse_result=_synthetic_parse_result(
                    text=text,
                    source=source,
                    intent="cancel",
                ),
            )
        return None

    pending_log, parse_result = pending

    if CANCEL_RE.match(normalized):
        mark_pending_status(
            db,
            pending_log=pending_log,
            status=CANCELLED_TRANSACTION_STATUS,
        )
        return TextTransactionResult(
            status="cancelled",
            reply_text=format_cancelled_response(),
            parse_result=clone_parsed_message(parse_result, need_confirmation=False),
        )

    if YES_CONFIRMATION_RE.match(normalized):
        return _save_transaction_from_parse_result(
            db=db,
            user_id=user_id,
            parse_result=clone_parsed_message(parse_result, need_confirmation=False),
            pending_log=pending_log,
        )

    if EDIT_RE.match(normalized) or _looks_like_missing_amount_reply(parse_result, normalized):
        edited = _apply_pending_transaction_edit(
            db=db,
            parse_result=parse_result,
            text=normalized,
        )
        update_pending_transaction(
            db,
            pending_log=pending_log,
            parse_result=edited,
            raw_message=text,
        )
        return TextTransactionResult(
            status="edit_updated",
            reply_text=_format_confirmation_request(edited),
            parse_result=edited,
        )

    return None


def _handle_lightweight_message(
    *,
    db: Session,
    user_id: int,
    text: str,
    source: str,
) -> TextTransactionResult | None:
    normalized = normalize_text(text)
    if THANKS_RE.match(normalized):
        return TextTransactionResult(
            status="small_talk",
            reply_text="Sama-sama. Kalau ada transaksi lagi, tinggal kirim aja.",
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="small_talk",
            ),
        )
    if ACK_RE.match(normalized):
        return TextTransactionResult(
            status="acknowledged",
            reply_text="Siap.",
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="acknowledged",
            ),
        )
    if TOP_EXPENSE_RE.search(normalized):
        return TextTransactionResult(
            status="top_expense",
            reply_text=_format_top_expense_response(db, user_id),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="top_expense",
            ),
        )
    if SPENDING_CHECK_RE.search(normalized):
        return TextTransactionResult(
            status="spending_check",
            reply_text=_format_spending_check_response(db, user_id),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="spending_check",
            ),
        )

    category_match = CATEGORY_SUMMARY_RE.search(normalized)
    if category_match:
        category_name = _category_name_from_alias(category_match.group("category"))
        return TextTransactionResult(
            status="category_summary",
            reply_text=_format_category_summary_response(db, user_id, category_name),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="category_summary",
            ),
        )

    return None


def _apply_pending_transaction_edit(
    *,
    db: Session,
    parse_result: ParsedMessage,
    text: str,
) -> ParsedMessage:
    amount = parse_amount(text) or parse_result.amount
    transaction_type = _detect_type_edit(text) or parse_result.type
    category = _detect_category_edit(db, text) or parse_result.category
    transaction_date = _detect_date_edit(text) or parse_result.transaction_date
    description = _detect_description_edit(text) or parse_result.description
    reasons = [reason for reason in parse_result.reasons if reason != "missing_amount"]
    if amount is None and "missing_amount" not in reasons:
        reasons.append("missing_amount")

    confidence = max(parse_result.confidence, 0.80 if amount else 0.55)
    if amount is not None and transaction_type is not None and category is not None:
        confidence = max(confidence, 0.85)

    return clone_parsed_message(
        parse_result,
        type=transaction_type,
        amount=amount,
        category=category,
        description=description,
        transaction_date=transaction_date,
        confidence=min(confidence, 0.95),
        need_confirmation=True,
        reasons=reasons,
    )


def _apply_forced_transaction_type(
    parse_result: ParsedMessage,
    *,
    transaction_type: str,
) -> ParsedMessage:
    if parse_result.intent != INTENT_ADD_TRANSACTION:
        return parse_result

    reasons = list(parse_result.reasons)
    reason = f"forced_{transaction_type}_from_menu"
    if reason not in reasons:
        reasons.append(reason)

    return clone_parsed_message(
        parse_result,
        type=transaction_type,
        reasons=reasons,
    )


def _looks_like_missing_amount_reply(parse_result: ParsedMessage, text: str) -> bool:
    if parse_result.amount is not None:
        return False
    amount = parse_amount(text)
    if amount is None:
        return False
    words = re.findall(r"[a-zA-Z\u00c0-\u024f]+", text)
    return len(words) <= 3


def _detect_type_edit(text: str) -> str | None:
    if re.search(r"\b(pemasukan|income|masuk|gaji|uang saku|dapat|refund|cashback)\b", text):
        return "income"
    if re.search(r"\b(pengeluaran|expense|keluar|bayar|beli|jajan|belanja|habis)\b", text):
        return "expense"
    return None


def _detect_category_edit(db: Session, text: str) -> str | None:
    categories = db.scalars(select(Category)).all()
    for category in categories:
        if category.name.lower() in text:
            return category.name

    aliases = {
        "makan": "Makanan",
        "makanan": "Makanan",
        "kopi": "Makanan",
        "transport": "Transportasi",
        "bensin": "Transportasi",
        "kos": "Tagihan",
        "tagihan": "Tagihan",
        "belanja": "Belanja",
        "hiburan": "Hiburan",
        "kesehatan": "Kesehatan",
        "pendidikan": "Pendidikan",
        "uang saku": "Uang Saku",
        "gaji": "Gaji",
    }
    for alias, category_name in aliases.items():
        if alias in text:
            return category_name
    return None


def _detect_date_edit(text: str) -> date | None:
    match = parse_transaction_date(text, date.today())
    return match.value if match else None


def _detect_description_edit(text: str) -> str | None:
    match = re.search(r"\b(?:catatan|deskripsi|note)\s+(.+)$", text)
    if not match:
        return None
    description = re.sub(r"\s+", " ", match.group(1)).strip(" -,.")
    return description or None


def _format_command_response(
    db: Session,
    user_id: int,
    parse_result: ParsedMessage,
) -> str:
    period = _format_period(parse_result.period)

    if parse_result.intent == INTENT_GET_BALANCE:
        return _format_balance_response(db, user_id)
    if parse_result.intent == INTENT_LIST_EXPENSE:
        return _format_transaction_list_response(
            db,
            user_id,
            transaction_type="expense",
            period=parse_result.period,
        )
    if parse_result.intent == INTENT_LIST_INCOME:
        return _format_transaction_list_response(
            db,
            user_id,
            transaction_type="income",
            period=parse_result.period,
        )
    if parse_result.intent == INTENT_GET_REPORT:
        return _format_report_summary_response(db, user_id, parse_result.period)
    if parse_result.intent == INTENT_EXPORT_PDF:
        return f"Perintah export PDF laporan {period} terdeteksi. PDF service akan memproses permintaan ini."
    if parse_result.intent == INTENT_RECENT_TRANSACTIONS:
        return _format_recent_transactions_response(db, user_id)
    if parse_result.intent == INTENT_DELETE_LAST_TRANSACTION:
        return "Aku menemukan perintah hapus transaksi terakhir. Fitur ini butuh konfirmasi sebelum transaksi dihapus."
    if parse_result.intent == INTENT_HELP:
        return format_help_response()
    if parse_result.intent == INTENT_LINK_ACCOUNT:
        return (
            "Silakan daftar atau login di dashboard Sakoo, buka Connected Bots, "
            "buat kode linking, lalu kirim: hubungkan KODE."
        )
    if parse_result.intent == INTENT_UNKNOWN:
        return format_unknown_response()
    return "Perintah terdeteksi."


def build_balance_response(db: Session, user_id: int) -> str:
    return _format_balance_response(db, user_id)


def build_transaction_list_response(
    db: Session,
    user_id: int,
    *,
    transaction_type: str,
    period: str | None,
) -> str:
    return _format_transaction_list_response(
        db,
        user_id,
        transaction_type=transaction_type,
        period=period,
    )


def build_recent_transactions_response(db: Session, user_id: int) -> str:
    return _format_recent_transactions_response(db, user_id)


def build_report_summary_response(
    db: Session,
    user_id: int,
    period: str | None,
) -> str:
    return _format_report_summary_response(db, user_id, period)


def _format_period(period: str | None) -> str:
    labels = {
        "day": "hari ini",
        "week": "minggu ini",
        "month": "bulan ini",
        "yesterday": "kemarin",
    }
    return labels.get(period or "", "terbaru")


def _format_confirmation_request(parse_result: ParsedMessage) -> str:
    return format_confirmation_request(
        transaction_type=parse_result.type,
        amount=parse_result.amount,
        category=parse_result.category,
        missing_amount=parse_result.amount is None,
    )


def _format_saved_transaction(
    db: Session,
    user_id: int,
    transaction: Transaction,
    category: Category | None,
) -> str:
    balance_after = calculate_balance(db, user_id)
    context_note = _build_saved_transaction_context_note(
        db,
        user_id,
        transaction=transaction,
        category=category,
    )
    return format_saved_transaction_template(
        transaction,
        category,
        style=_reply_style(),
        balance_after=balance_after,
        context_note=context_note,
    )


def _format_balance_response(db: Session, user_id: int) -> str:
    income_total = sum_transactions(db, user_id, transaction_type="income")
    expense_total = sum_transactions(db, user_id, transaction_type="expense")
    balance = income_total - expense_total
    return (
        "Saldo kamu saat ini:\n\n"
        f"Pemasukan: {format_rupiah(income_total)}\n"
        f"Pengeluaran: {format_rupiah(expense_total)}\n"
        f"Sisa saldo: {format_rupiah(balance)}"
    )


def _format_transaction_list_response(
    db: Session,
    user_id: int,
    *,
    transaction_type: str,
    period: str | None,
) -> str:
    start_date, end_date = _period_bounds(period)
    transactions = list_transactions(
        db,
        user_id,
        transaction_type=transaction_type,
        start_date=start_date,
        end_date=end_date,
        limit=5,
    )
    label = "pengeluaran" if transaction_type == "expense" else "pemasukan"
    if not transactions:
        return f"Belum ada {label} {_format_period(period)}."

    lines = [
        f"{index}. {item.transaction_date.isoformat()} - "
        f"{format_rupiah(item.amount)} - "
        f"{item.category.name if item.category else 'Tanpa kategori'}"
        f"{f' - {item.description}' if item.description else ''}"
        for index, item in enumerate(transactions, start=1)
    ]
    return f"List {label} {_format_period(period)}:\n\n" + "\n".join(lines)


def _format_recent_transactions_response(db: Session, user_id: int) -> str:
    transactions = list_transactions(db, user_id, limit=5)
    if not transactions:
        return "Belum ada riwayat transaksi."

    lines = [
        f"{index}. {item.transaction_date.isoformat()} - "
        f"{'Pemasukan' if item.type == 'income' else 'Pengeluaran'} - "
        f"{format_rupiah(item.amount)} - "
        f"{item.category.name if item.category else 'Tanpa kategori'}"
        for index, item in enumerate(transactions, start=1)
    ]
    return "Riwayat transaksi terbaru:\n\n" + "\n".join(lines)


def _format_report_summary_response(
    db: Session,
    user_id: int,
    period: str | None,
) -> str:
    start_date, end_date = _period_bounds(period or "month")
    income_total = sum_transactions(
        db,
        user_id,
        transaction_type="income",
        start_date=start_date,
        end_date=end_date,
    )
    expense_total = sum_transactions(
        db,
        user_id,
        transaction_type="expense",
        start_date=start_date,
        end_date=end_date,
    )
    net = income_total - expense_total
    insight = _build_report_insight(
        db,
        user_id,
        start_date=start_date,
        end_date=end_date,
        expense_total=expense_total,
    )
    insight_text = f"\n\n{insight}" if insight else ""
    return (
        f"Laporan {_format_period(period or 'month')}:\n\n"
        f"Pemasukan: {format_rupiah(income_total)}\n"
        f"Pengeluaran: {format_rupiah(expense_total)}\n"
        f"Saldo bersih: {format_rupiah(net)}"
        f"{insight_text}"
    )


def _format_spending_check_response(db: Session, user_id: int) -> str:
    today = date.today()
    today_expense = sum_transactions(
        db,
        user_id,
        transaction_type="expense",
        start_date=today,
        end_date=today,
    )
    month_start = today.replace(day=1)
    month_expense = sum_transactions(
        db,
        user_id,
        transaction_type="expense",
        start_date=month_start,
        end_date=today,
    )
    elapsed_days = max(today.day, 1)
    daily_average = month_expense / Decimal(elapsed_days)

    if today_expense == 0:
        verdict = "Belum ada pengeluaran hari ini."
    elif daily_average and today_expense > daily_average * Decimal("1.5"):
        verdict = "Hari ini agak lebih tinggi dari rata-rata bulan ini."
    else:
        verdict = "Masih relatif aman dibanding rata-rata bulan ini."

    return (
        f"Pengeluaran hari ini: {format_rupiah(today_expense)}\n"
        f"Rata-rata harian bulan ini: {format_rupiah(daily_average)}\n\n"
        f"{verdict}"
    )


def _format_top_expense_response(db: Session, user_id: int) -> str:
    today = date.today()
    start_date = today.replace(day=1)
    top_category = top_expense_category(
        db,
        user_id,
        start_date=start_date,
        end_date=today,
    )
    if not top_category:
        return "Belum ada pengeluaran bulan ini."

    category_name, total = top_category
    return (
        "Pengeluaran terbesar bulan ini:\n\n"
        f"{category_name}: {format_rupiah(total)}"
    )


def _format_category_summary_response(
    db: Session,
    user_id: int,
    category_name: str,
) -> str:
    today = date.today()
    start_date = today.replace(day=1)
    total = sum_category_expense(
        db,
        user_id,
        category_name=category_name,
        start_date=start_date,
        end_date=today,
    )
    return (
        f"{category_name} bulan ini: {format_rupiah(total)}.\n"
        "Aku hitung dari transaksi yang sudah tercatat."
    )


def _period_bounds(period: str | None) -> tuple[date | None, date | None]:
    today = date.today()
    if period == "day":
        return today, today
    if period == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday
    if period == "week":
        return today - timedelta(days=today.weekday()), today
    if period == "month":
        return today.replace(day=1), today
    return None, None


def _build_saved_transaction_context_note(
    db: Session,
    user_id: int,
    *,
    transaction: Transaction,
    category: Category | None,
) -> str | None:
    notes: list[str] = []
    if transaction.type == "expense":
        day_total = sum_transactions(
            db,
            user_id,
            transaction_type="expense",
            start_date=transaction.transaction_date,
            end_date=transaction.transaction_date,
        )
        if day_total >= Decimal("100000"):
            notes.append(f"Hari ini pengeluaranmu sudah {format_rupiah(day_total)}.")

    if category is not None:
        category_count = count_user_category_transactions(
            db,
            user_id,
            category.id,
        )
        if category_count >= 3:
            notes.append(f"Masuk ke {category.name}, kategori yang cukup sering kamu pakai.")

    return " ".join(notes) if notes else None


def _build_report_insight(
    db: Session,
    user_id: int,
    *,
    start_date: date | None,
    end_date: date | None,
    expense_total: Decimal,
) -> str | None:
    if expense_total <= 0:
        return "Belum ada pengeluaran di periode ini."

    top_category = top_expense_category(
        db,
        user_id,
        start_date=start_date,
        end_date=end_date,
    )
    if not top_category:
        return None

    category_name, total = top_category
    percentage = (total / expense_total * Decimal("100")).quantize(Decimal("1"))
    return (
        f"Insight: paling besar di {category_name}, "
        f"{format_rupiah(total)} ({percentage}% dari pengeluaran)."
    )


def _category_name_from_alias(alias: str) -> str:
    normalized = alias.lower()
    if normalized in {"makan", "makanan", "kopi"}:
        return "Makanan"
    if normalized in {"transport", "bensin"}:
        return "Transportasi"
    if normalized in {"kos", "tagihan"}:
        return "Tagihan"
    return normalized.title()


def _synthetic_parse_result(*, text: str, source: str, intent: str) -> ParsedMessage:
    return ParsedMessage(
        intent=intent,
        type=None,
        amount=None,
        category=None,
        description=normalize_text(text) or None,
        transaction_date=date.today(),
        source=source,
        confidence=1.0,
        need_confirmation=False,
        reasons=[],
    )


def _platform_from_source(source: str) -> str:
    normalized = source.strip().lower()
    if normalized.startswith("telegram"):
        return "telegram"
    if normalized.startswith("whatsapp"):
        return "whatsapp"
    if normalized.startswith("dashboard"):
        return "dashboard"
    return "system"


def _reply_style() -> str:
    style = get_settings().bot_reply_style.strip().lower()
    if style in {"short", "friendly", "detailed"}:
        return style
    return "friendly"
