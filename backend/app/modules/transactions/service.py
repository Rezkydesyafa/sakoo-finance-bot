import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BotLog, Category, Receipt, Transaction, User, UserPreference
from app.modules.bot.conversation_state import (
    CANCELLED_TRANSACTION_STATUS,
    CONFIRMED_TRANSACTION_STATUS,
    PENDING_TRANSACTION_TTL,
    clone_parsed_message,
    get_pending_transaction,
    mark_pending_status,
    store_pending_transaction,
    update_pending_transaction,
)
from app.modules.llm.base import LlmProviderError
from app.modules.llm.llm_router import LlmRateLimitExceeded, answer_finance_question_with_llm
from app.modules.bot.response_templates import (
    format_cancelled_response,
    format_confirmation_request,
    format_help_response,
    format_llm_error_response,
    format_no_pending_response,
    format_rate_limit_response,
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
    INTENT_FINANCE_CHAT,
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
RESET_CONFIRM_RE = re.compile(r"^\s*(?:ya\s+)?reset\s*$", re.IGNORECASE)
RESET_REQUEST_RE = re.compile(
    r"\b(?:kosongkan|reset|bersihkan|hapus semua)\b.*\b(?:pengeluaran|pemasukan|transaksi|semua)\b",
    re.IGNORECASE,
)
BOT_PROFILE_RE = re.compile(
    r"\b(?:kamu siapa|siapa kamu|bisa bantu apa|bantu saya apa|fitur kamu|kamu bisa apa)\b",
    re.IGNORECASE,
)
SPENDING_CHECK_RE = re.compile(r"\b(?:boros|hemat|pengeluaran.*hari ini|hari ini.*keluar)\b", re.IGNORECASE)
PURCHASE_LIST_RE = re.compile(
    r"\b(?:bulan ini|minggu ini|hari ini)\b.*\b(?:beli|belanja|jajan)\b.*\b(?:apa aja|apa saja)\b|"
    r"\b(?:apa aja|apa saja)\b.*\b(?:dibeli|aku beli|saya beli|belanja)\b",
    re.IGNORECASE,
)
TOP_EXPENSE_RE = re.compile(r"\b(?:pengeluaran terbesar|paling gede|terbesar apa|top pengeluaran)\b", re.IGNORECASE)
SAVING_ADVICE_RE = re.compile(r"\b(?:saran hemat|tips hemat|cara hemat|hemat minggu ini)\b", re.IGNORECASE)
CASHFLOW_REASON_RE = re.compile(r"\b(?:kenapa.*(?:saldo|uang).*(?:habis|cepat habis)|saldo.*cepat habis)\b", re.IGNORECASE)
WEEK_COMPARE_RE = re.compile(r"\b(?:bandingkan|dibanding|compare).*(?:minggu ini|minggu lalu)|\bminggu ini.*minggu lalu\b", re.IGNORECASE)
CUTBACK_RE = re.compile(r"\b(?:apa yang harus dikurangi|kurangi apa|yang perlu dikurangi|pengeluaran.*dikurangi)\b", re.IGNORECASE)
INCOME_SOURCE_RE = re.compile(
    r"\b(?:pemasukan|pemsukan|income|uang masuk)\b.*\b(?:dari mana|sumber|apa aja|apa saja)\b",
    re.IGNORECASE,
)
SEARCH_TRANSACTION_RE = re.compile(r"^\s*(?:cari|search|temukan)\s+(?P<keyword>.+?)\s*$", re.IGNORECASE)
FINANCE_HEALTH_RE = re.compile(
    r"\b(?:aman|sehat|gimana|bagaimana|kondisi)\b.*\b(?:keuangan|bulan ini|saldo|cashflow)\b|"
    r"\b(?:keuangan|bulan ini|saldo|cashflow)\b.*\b(?:aman|sehat|gimana|bagaimana|kondisi)\b",
    re.IGNORECASE,
)
REPLY_STYLE_PREFERENCE_RE = re.compile(
    r"\b(?:gaya bahasa|bahasa|respon)\s+(?P<style>santai|formal|detail|rinci|singkat|pendek)\b",
    re.IGNORECASE,
)
CATEGORY_SUMMARY_RE = re.compile(
    r"\b(?P<category>makan(?:an)?|kopi|transport|bensin|tagihan|belanja|hiburan|kesehatan|pendidikan|kos)\b.*\b(?:berapa|total|bulan ini|minggu ini|hari ini)\b",
    re.IGNORECASE,
)
FINANCE_CHAT_RE = re.compile(
    r"\b(?:uang|keuangan|finansial|saldo|pengeluaran|pemasukan|transaksi|laporan|"
    r"budget|anggaran|hemat|boros|tabung|tabungan|gaji|struk|ocr|kategori|"
    r"dashboard|sakoo|utang|hutang|piutang|cashflow|pdf)\b",
    re.IGNORECASE,
)
RESET_MESSAGE_TYPE = "transaction_reset"
PENDING_RESET_STATUS = "pending_reset"
CONFIRMED_RESET_STATUS = "confirmed_reset"
CANCELLED_RESET_STATUS = "cancelled_reset"
EXPIRED_RESET_STATUS = "expired_reset"


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
    reset_result = _handle_transaction_reset_reply(
        db=db,
        user_id=user_id,
        text=text,
        source=source,
    )
    if reset_result is not None:
        return reset_result

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
        if parse_result.intent in {INTENT_UNKNOWN, INTENT_FINANCE_CHAT}:
            llm_chat = _handle_llm_finance_chat(
                db=db,
                user_id=user_id,
                text=text,
                source=source,
                parse_result=parse_result,
            )
            if llm_chat is not None:
                return llm_chat
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


def _handle_transaction_reset_reply(
    *,
    db: Session,
    user_id: int,
    text: str,
    source: str,
) -> TextTransactionResult | None:
    normalized = normalize_text(text)
    pending = _get_pending_transaction_reset(db, user_id=user_id)
    if pending is not None:
        reset_type = str((pending.parsed_result or {}).get("transaction_type") or "all")
        label = _reset_type_label(reset_type)
        if CANCEL_RE.match(normalized):
            pending.status = CANCELLED_RESET_STATUS
            db.flush()
            return TextTransactionResult(
                status="reset_cancelled",
                reply_text=f"Oke, reset {label} aku batalkan. Data kamu tetap aman.",
                parse_result=_synthetic_parse_result(
                    text=text,
                    source=source,
                    intent="reset_cancelled",
                ),
            )
        if RESET_CONFIRM_RE.match(normalized):
            deleted = _execute_transaction_reset(db, user_id=user_id, reset_type=reset_type)
            pending.status = CONFIRMED_RESET_STATUS
            db.flush()
            return TextTransactionResult(
                status="reset_done",
                reply_text=(
                    f"Selesai, {deleted} transaksi {label} sudah aku kosongkan.\n"
                    "Saldo dan laporan sekarang dihitung ulang dari data yang masih tersisa."
                ),
                parse_result=_synthetic_parse_result(
                    text=text,
                    source=source,
                    intent="reset_done",
                ),
            )
        return TextTransactionResult(
            status="reset_confirmation_pending",
            reply_text=(
                f"Masih ada permintaan reset {label} yang menunggu konfirmasi.\n"
                "Balas YA RESET untuk lanjut, atau batal."
            ),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="reset_confirmation_pending",
            ),
        )

    reset_type = _detect_reset_type(normalized)
    if reset_type is None:
        return None

    count = _count_reset_transactions(db, user_id=user_id, reset_type=reset_type)
    label = _reset_type_label(reset_type)
    if count == 0:
        return TextTransactionResult(
            status="reset_empty",
            reply_text=f"Belum ada transaksi {label} yang bisa dikosongkan.",
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="reset_empty",
            ),
        )

    _store_pending_transaction_reset(
        db,
        user_id=user_id,
        platform=_platform_from_source(source),
        raw_message=text,
        reset_type=reset_type,
    )
    return TextTransactionResult(
        status="reset_needs_confirmation",
        reply_text=(
            f"Aku bisa kosongkan {label}, tapi ini akan menghapus {count} transaksi.\n"
            "Kalau sudah yakin, balas YA RESET.\n"
            "Kalau berubah pikiran, balas batal."
        ),
        parse_result=_synthetic_parse_result(
            text=text,
            source=source,
            intent="reset_needs_confirmation",
        ),
    )


def _get_pending_transaction_reset(db: Session, *, user_id: int) -> BotLog | None:
    pending = db.scalar(
        select(BotLog)
        .where(
            BotLog.user_id == user_id,
            BotLog.message_type == RESET_MESSAGE_TYPE,
            BotLog.status == PENDING_RESET_STATUS,
        )
        .order_by(BotLog.created_at.desc(), BotLog.id.desc())
    )
    if pending is None:
        return None
    created_at = pending.created_at if pending.created_at.tzinfo else pending.created_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created_at > PENDING_TRANSACTION_TTL:
        pending.status = EXPIRED_RESET_STATUS
        db.flush()
        return None
    return pending


def _store_pending_transaction_reset(
    db: Session,
    *,
    user_id: int,
    platform: str,
    raw_message: str,
    reset_type: str,
) -> None:
    db.add(
        BotLog(
            user_id=user_id,
            platform=platform,
            message_type=RESET_MESSAGE_TYPE,
            raw_message=raw_message,
            parsed_result={
                "kind": "transaction_reset",
                "transaction_type": reset_type,
            },
            status=PENDING_RESET_STATUS,
        )
    )
    db.flush()


def _detect_reset_type(text: str) -> str | None:
    if not RESET_REQUEST_RE.search(text):
        return None
    has_expense = "pengeluaran" in text
    has_income = "pemasukan" in text
    if has_expense and has_income:
        return "all"
    if "transaksi" in text or "semua" in text:
        return "all"
    if has_expense:
        return "expense"
    if has_income:
        return "income"
    return None


def _count_reset_transactions(db: Session, *, user_id: int, reset_type: str) -> int:
    query = select(func.count(Transaction.id)).where(Transaction.user_id == user_id)
    if reset_type in {"expense", "income"}:
        query = query.where(Transaction.type == reset_type)
    return int(db.scalar(query) or 0)


def _execute_transaction_reset(db: Session, *, user_id: int, reset_type: str) -> int:
    query = select(Transaction).where(Transaction.user_id == user_id)
    if reset_type in {"expense", "income"}:
        query = query.where(Transaction.type == reset_type)
    transactions = list(db.scalars(query))
    transaction_ids = [item.id for item in transactions]
    if transaction_ids:
        for receipt in db.scalars(select(Receipt).where(Receipt.transaction_id.in_(transaction_ids))):
            receipt.transaction_id = None
        for transaction in transactions:
            db.delete(transaction)
    return len(transactions)


def _reset_type_label(reset_type: str) -> str:
    if reset_type == "expense":
        return "pengeluaran"
    if reset_type == "income":
        return "pemasukan"
    return "pengeluaran dan pemasukan"


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
        if (
            CANCEL_RE.match(normalized)
            or YES_CONFIRMATION_RE.match(normalized)
            or EDIT_RE.match(normalized)
        ):
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


def _handle_llm_finance_chat(
    *,
    db: Session,
    user_id: int,
    text: str,
    source: str,
    parse_result: ParsedMessage,
) -> TextTransactionResult | None:
    try:
        answer = answer_finance_question_with_llm(
            text,
            context=_build_llm_finance_context(db, user_id),
            user_id=user_id,
            db=db,
        )
    except LlmRateLimitExceeded as exc:
        return TextTransactionResult(
            status="llm_rate_limited",
            reply_text=format_rate_limit_response(),
            parse_result=parse_result,
            error_message=exc.detail,
        )
    except LlmProviderError as exc:
        return TextTransactionResult(
            status=INTENT_UNKNOWN,
            reply_text=format_llm_error_response(),
            parse_result=parse_result,
            error_message=exc.detail,
        )

    return TextTransactionResult(
        status="finance_chat",
        reply_text=answer,
        parse_result=_synthetic_parse_result(
            text=text,
            source=source,
            intent="finance_chat",
        ),
    )


def _handle_lightweight_message(
    *,
    db: Session,
    user_id: int,
    text: str,
    source: str,
) -> TextTransactionResult | None:
    normalized = normalize_text(text)
    reply_style = _detect_reply_style_preference(normalized)
    if reply_style:
        return _save_reply_style_preference(
            db=db,
            user_id=user_id,
            text=text,
            source=source,
            reply_style=reply_style,
        )
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
    if BOT_PROFILE_RE.search(normalized):
        return TextTransactionResult(
            status="bot_profile",
            reply_text=_format_bot_profile_response(db, user_id),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="bot_profile",
            ),
        )
    if PURCHASE_LIST_RE.search(normalized):
        return TextTransactionResult(
            status="purchase_list",
            reply_text=_format_purchase_list_response(db, user_id, normalized),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="purchase_list",
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
    if SAVING_ADVICE_RE.search(normalized):
        return TextTransactionResult(
            status="saving_advice",
            reply_text=_format_saving_advice_response(db, user_id),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="saving_advice",
            ),
        )
    if CASHFLOW_REASON_RE.search(normalized):
        return TextTransactionResult(
            status="cashflow_reason",
            reply_text=_format_cashflow_reason_response(db, user_id),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="cashflow_reason",
            ),
        )
    if WEEK_COMPARE_RE.search(normalized):
        return TextTransactionResult(
            status="week_compare",
            reply_text=_format_week_compare_response(db, user_id),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="week_compare",
            ),
        )
    if CUTBACK_RE.search(normalized):
        return TextTransactionResult(
            status="cutback_advice",
            reply_text=_format_cutback_advice_response(db, user_id),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="cutback_advice",
            ),
        )
    if INCOME_SOURCE_RE.search(normalized):
        return TextTransactionResult(
            status="income_source",
            reply_text=_format_income_source_response(db, user_id),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="income_source",
            ),
        )
    if SPENDING_CHECK_RE.search(normalized):
        return TextTransactionResult(
            status="spending_check",
            reply_text=_format_spending_check_response(db, user_id, text=normalized),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="spending_check",
            ),
        )
    if FINANCE_HEALTH_RE.search(normalized):
        return TextTransactionResult(
            status="finance_health",
            reply_text=_format_finance_health_response(db, user_id),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="finance_health",
            ),
        )

    search_match = SEARCH_TRANSACTION_RE.match(normalized)
    if search_match:
        return TextTransactionResult(
            status="transaction_search",
            reply_text=_format_transaction_search_response(
                db,
                user_id,
                keyword=search_match.group("keyword"),
            ),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="transaction_search",
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
    description = _detect_description_edit(text)
    transaction_type = _detect_type_edit(text) or parse_result.type
    category = (
        parse_result.category
        if description is not None
        else _detect_category_edit(db, text) or parse_result.category
    )
    transaction_date = (
        parse_result.transaction_date
        if description is not None
        else _detect_date_edit(text) or parse_result.transaction_date
    )
    description = description or parse_result.description
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
        return (
            f"Siap, aku siapkan export PDF laporan {period}. "
            "Nanti file PDF akan aku kirim setelah selesai dibuat."
        )
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
    if parse_result.intent == INTENT_FINANCE_CHAT:
        return (
            "😅 Maaf, aku belum bisa jawab pertanyaan itu sekarang.\n\n"
            "Coba lagi nanti, atau tanya hal lain seputar keuanganmu! 💬"
        )
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
        transaction_date=parse_result.transaction_date,
        description=parse_result.description,
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
        style=_reply_style(db, user_id),
        balance_after=balance_after,
        context_note=context_note,
    )


def _format_balance_response(db: Session, user_id: int) -> str:
    income_total = sum_transactions(db, user_id, transaction_type="income")
    expense_total = sum_transactions(db, user_id, transaction_type="expense")
    balance = income_total - expense_total
    name = _user_first_name(db, user_id)
    return (
        f"Aku cek ya, {name}. Ini posisi saldomu saat ini:\n\n"
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
        newest_by_created=period is None,
    )
    label = "pengeluaran" if transaction_type == "expense" else "pemasukan"
    name = _user_first_name(db, user_id)
    if not transactions:
        return f"Belum ada {label} {_format_period(period)}, {name}. Kalau ada, kirim aja lewat chat."

    lines = [
        f"{index}. {item.transaction_date.isoformat()} - "
        f"{format_rupiah(item.amount)} - "
        f"{item.category.name if item.category else 'Tanpa kategori'}"
        f"{f' - {item.description}' if item.description else ''}"
        for index, item in enumerate(transactions, start=1)
    ]
    return f"Aku cek, {name}. List {label} {_format_period(period)} kamu:\n\n" + "\n".join(lines)


def _format_recent_transactions_response(db: Session, user_id: int) -> str:
    transactions = list_transactions(db, user_id, limit=5, newest_by_created=True)
    name = _user_first_name(db, user_id)
    if not transactions:
        return f"Belum ada riwayat transaksi, {name}."

    lines = [
        f"{index}. {item.transaction_date.isoformat()} - "
        f"{'Pemasukan' if item.type == 'income' else 'Pengeluaran'} - "
        f"{format_rupiah(item.amount)} - "
        f"{item.category.name if item.category else 'Tanpa kategori'}"
        for index, item in enumerate(transactions, start=1)
    ]
    return f"Aku ambil Riwayat transaksi terbaru kamu, {name}:\n\n" + "\n".join(lines)


def _format_bot_profile_response(db: Session, user_id: int) -> str:
    name = _user_first_name(db, user_id)
    return (
        f"Halo {name}. Aku Sakoo, asisten keuangan pribadi kamu.\n"
        "Aku bisa bantu catat transaksi, baca struk, cek saldo, bikin laporan, dan cari riwayat.\n"
        "Coba tanya: bulan ini aku beli apa saja, makanan berapa, atau saldo aman gak?"
    )


def _format_purchase_list_response(db: Session, user_id: int, text: str) -> str:
    if "hari ini" in text:
        period = "day"
    elif "minggu ini" in text:
        period = "week"
    else:
        period = "month"
    return _format_transaction_list_response(
        db,
        user_id,
        transaction_type="expense",
        period=period,
    )


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


def _format_spending_check_response(db: Session, user_id: int, *, text: str) -> str:
    today = date.today()
    if "hari ini" not in text:
        return _format_month_spending_check_response(db, user_id)

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


def _format_month_spending_check_response(db: Session, user_id: int) -> str:
    today = date.today()
    month_start = today.replace(day=1)
    month_expense = sum_transactions(
        db,
        user_id,
        transaction_type="expense",
        start_date=month_start,
        end_date=today,
    )
    month_income = sum_transactions(
        db,
        user_id,
        transaction_type="income",
        start_date=month_start,
        end_date=today,
    )
    top_category = top_expense_category(db, user_id, start_date=month_start, end_date=today)
    if month_income == 0 and month_expense > 0:
        verdict = "Belum ada pemasukan bulan ini, jadi pengeluaran perlu dijaga."
    elif month_expense <= month_income:
        verdict = "Masih aman, pengeluaran belum melewati pemasukan bulan ini."
    else:
        verdict = "Perlu direm, pengeluaran sudah melewati pemasukan bulan ini."
    top_line = (
        f"\nKategori terbesar: {top_category[0]} {format_rupiah(top_category[1])}"
        if top_category
        else ""
    )
    return (
        f"Pengeluaran bulan ini: {format_rupiah(month_expense)}\n"
        f"Pemasukan bulan ini: {format_rupiah(month_income)}"
        f"{top_line}\n\n"
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


def _format_saving_advice_response(db: Session, user_id: int) -> str:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    top_category = top_expense_category(db, user_id, start_date=week_start, end_date=today)
    if not top_category:
        return "Belum ada pengeluaran minggu ini. Mulai catat transaksi dulu biar sarannya akurat."

    category_name, total = top_category
    return (
        f"Minggu ini paling besar di {category_name}: {format_rupiah(total)}.\n"
        "Saran cepat: tahan transaksi kecil yang berulang di kategori itu dulu."
    )


def _format_income_source_response(db: Session, user_id: int) -> str:
    today = date.today()
    start_date = today.replace(day=1)
    transactions = list_transactions(
        db,
        user_id,
        transaction_type="income",
        start_date=start_date,
        end_date=today,
        limit=5,
    )
    if not transactions:
        return "Belum ada pemasukan bulan ini."

    lines = [
        f"{index}. {item.category.name if item.category else 'Tanpa kategori'} - "
        f"{format_rupiah(item.amount)}"
        f"{f' - {item.description}' if item.description else ''}"
        for index, item in enumerate(transactions, start=1)
    ]
    return "Pemasukan bulan ini dari:\n\n" + "\n".join(lines)


def _format_week_compare_response(db: Session, user_id: int) -> str:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    last_week_start = week_start - timedelta(days=7)
    last_week_end = week_start - timedelta(days=1)
    current = sum_transactions(
        db,
        user_id,
        transaction_type="expense",
        start_date=week_start,
        end_date=today,
    )
    previous = sum_transactions(
        db,
        user_id,
        transaction_type="expense",
        start_date=last_week_start,
        end_date=last_week_end,
    )
    diff = current - previous
    if previous == 0 and current == 0:
        verdict = "Belum ada pengeluaran di dua minggu ini."
    elif diff <= 0:
        verdict = f"Lebih hemat {format_rupiah(abs(diff))} dari minggu lalu."
    else:
        verdict = f"Naik {format_rupiah(diff)} dari minggu lalu."
    return (
        f"Minggu ini: {format_rupiah(current)}\n"
        f"Minggu lalu: {format_rupiah(previous)}\n\n"
        f"{verdict}"
    )


def _format_cutback_advice_response(db: Session, user_id: int) -> str:
    today = date.today()
    month_start = today.replace(day=1)
    top_category = top_expense_category(db, user_id, start_date=month_start, end_date=today)
    if not top_category:
        return "Belum ada pengeluaran bulan ini, jadi belum ada yang perlu dikurangi."

    category_name, total = top_category
    return (
        f"Yang paling layak dikurangi: {category_name} ({format_rupiah(total)} bulan ini).\n"
        "Mulai dari transaksi kecil yang berulang di kategori itu."
    )


def _format_finance_health_response(db: Session, user_id: int) -> str:
    today = date.today()
    month_start = today.replace(day=1)
    income_total = sum_transactions(
        db,
        user_id,
        transaction_type="income",
        start_date=month_start,
        end_date=today,
    )
    expense_total = sum_transactions(
        db,
        user_id,
        transaction_type="expense",
        start_date=month_start,
        end_date=today,
    )
    net = income_total - expense_total
    if income_total == 0 and expense_total > 0:
        verdict = "Belum aman, bulan ini belum ada pemasukan tercatat."
    elif net >= 0:
        verdict = "Masih aman, pemasukan bulan ini menutup pengeluaran."
    else:
        verdict = "Perlu direm, pengeluaran bulan ini sudah melewati pemasukan."
    return (
        f"Pemasukan bulan ini: {format_rupiah(income_total)}\n"
        f"Pengeluaran bulan ini: {format_rupiah(expense_total)}\n"
        f"Selisih: {format_rupiah(net)}\n\n"
        f"{verdict}"
    )


def _format_transaction_search_response(
    db: Session,
    user_id: int,
    *,
    keyword: str,
) -> str:
    normalized = re.sub(r"\s+", " ", keyword).strip(" -,.").lower()
    if len(normalized) < 2:
        return "Kata kunci terlalu pendek. Contoh: cari kopi atau cari gojek."

    pattern = f"%{normalized}%"
    transactions = list(
        db.scalars(
            select(Transaction)
            .join(Category, Transaction.category_id == Category.id, isouter=True)
            .where(
                Transaction.user_id == user_id,
                or_(
                    func.lower(Transaction.description).like(pattern),
                    func.lower(Category.name).like(pattern),
                ),
            )
            .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
            .limit(5)
        )
    )
    if not transactions:
        return f"Aku belum menemukan transaksi untuk '{normalized}'."

    lines = [
        f"{index}. {item.transaction_date.isoformat()} - "
        f"{'Pemasukan' if item.type == 'income' else 'Pengeluaran'} - "
        f"{format_rupiah(item.amount)} - "
        f"{item.category.name if item.category else 'Tanpa kategori'}"
        f"{f' - {item.description}' if item.description else ''}"
        for index, item in enumerate(transactions, start=1)
    ]
    return f"Hasil pencarian '{normalized}':\n\n" + "\n".join(lines)


def _format_cashflow_reason_response(db: Session, user_id: int) -> str:
    today = date.today()
    month_start = today.replace(day=1)
    top_category = top_expense_category(db, user_id, start_date=month_start, end_date=today)
    month_expense = sum_transactions(
        db,
        user_id,
        transaction_type="expense",
        start_date=month_start,
        end_date=today,
    )
    if not top_category:
        return "Aku belum lihat penyebabnya karena belum ada pengeluaran bulan ini."

    category_name, total = top_category
    return (
        f"Saldo cepat habis paling mungkin karena {category_name}: {format_rupiah(total)}.\n"
        f"Total pengeluaran bulan ini: {format_rupiah(month_expense)}."
    )


def _detect_reply_style_preference(text: str) -> str | None:
    match = REPLY_STYLE_PREFERENCE_RE.search(text)
    if not match:
        return None
    style = match.group("style").lower()
    if style == "santai":
        return "friendly"
    if style in {"formal", "detail", "rinci"}:
        return "detailed"
    if style in {"singkat", "pendek"}:
        return "short"
    return None


def _save_reply_style_preference(
    *,
    db: Session,
    user_id: int,
    text: str,
    source: str,
    reply_style: str,
) -> TextTransactionResult:
    preference = db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))
    if preference is None:
        preference = UserPreference(user_id=user_id, reply_style=reply_style)
        db.add(preference)
    else:
        preference.reply_style = reply_style
    db.flush()

    labels = {
        "friendly": "lebih santai",
        "detailed": "lebih formal dan detail",
        "short": "lebih singkat",
    }
    return TextTransactionResult(
        status="preference_updated",
        reply_text=f"Oke, gaya bahasa aku buat {labels[reply_style]}.",
        parse_result=_synthetic_parse_result(
            text=text,
            source=source,
            intent="preference_updated",
        ),
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


def _build_llm_finance_context(db: Session, user_id: int) -> str:
    today = date.today()
    name = _user_first_name(db, user_id)
    month_start = today.replace(day=1)
    income_total = sum_transactions(db, user_id, transaction_type="income")
    expense_total = sum_transactions(db, user_id, transaction_type="expense")
    month_expense = sum_transactions(
        db,
        user_id,
        transaction_type="expense",
        start_date=month_start,
        end_date=today,
    )
    month_income = sum_transactions(
        db,
        user_id,
        transaction_type="income",
        start_date=month_start,
        end_date=today,
    )
    top_category = top_expense_category(
        db,
        user_id,
        start_date=month_start,
        end_date=today,
    )
    recent = list_transactions(db, user_id, limit=5, newest_by_created=True)
    week_start = today - timedelta(days=today.weekday())
    last_week_start = week_start - timedelta(days=7)
    last_week_end = week_start - timedelta(days=1)
    week_expense = sum_transactions(
        db,
        user_id,
        transaction_type="expense",
        start_date=week_start,
        end_date=today,
    )
    last_week_expense = sum_transactions(
        db,
        user_id,
        transaction_type="expense",
        start_date=last_week_start,
        end_date=last_week_end,
    )
    recent_lines = [
        f"{item.transaction_date.isoformat()} {item.type} {format_rupiah(item.amount)} "
        f"{item.category.name if item.category else 'Tanpa kategori'} "
        f"{item.description or ''}".strip()
        for item in recent
    ]
    top_text = (
        f"{top_category[0]} {format_rupiah(top_category[1])}"
        if top_category
        else "belum ada"
    )
    return "\n".join(
        [
            f"Nama user: {name}",
            f"Saldo total: {format_rupiah(income_total - expense_total)}",
            f"Pemasukan total: {format_rupiah(income_total)}",
            f"Pengeluaran total: {format_rupiah(expense_total)}",
            f"Pemasukan bulan ini: {format_rupiah(month_income)}",
            f"Pengeluaran bulan ini: {format_rupiah(month_expense)}",
            f"Pengeluaran minggu ini: {format_rupiah(week_expense)}",
            f"Pengeluaran minggu lalu: {format_rupiah(last_week_expense)}",
            f"Kategori pengeluaran terbesar bulan ini: {top_text}",
            "Transaksi terbaru: " + ("; ".join(recent_lines) if recent_lines else "belum ada"),
        ]
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
    month_start = transaction.transaction_date.replace(day=1)
    month_expense = sum_transactions(
        db,
        user_id,
        transaction_type="expense",
        start_date=month_start,
        end_date=transaction.transaction_date,
    )
    top_category = top_expense_category(
        db,
        user_id,
        start_date=month_start,
        end_date=transaction.transaction_date,
    )
    notes.append(f"Pengeluaran bulan ini: {format_rupiah(month_expense)}.")
    if top_category:
        notes.append(
            f"Kategori terbesar: {top_category[0]} {format_rupiah(top_category[1])}."
        )

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


def _reply_style(db: Session | None = None, user_id: int | None = None) -> str:
    if db is not None and user_id is not None:
        preference = db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))
        if preference and preference.reply_style in {"short", "friendly", "detailed"}:
            return preference.reply_style

    style = get_settings().bot_reply_style.strip().lower()
    if style in {"short", "friendly", "detailed"}:
        return style
    return "friendly"


def _user_first_name(db: Session, user_id: int) -> str:
    name = db.scalar(select(User.name).where(User.id == user_id)) or ""
    first = str(name).strip().split(" ", 1)[0]
    return first or "kamu"
