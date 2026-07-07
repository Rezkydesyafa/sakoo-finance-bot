import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import BotLog, Category, Receipt, Transaction, User, UserPreference
from app.modules.budgets.service import (
    find_visible_expense_category_by_name,
    get_budget_for_category,
    get_budget_overview,
    upsert_category_budget,
)
from app.modules.bot.conversation_state import (
    CANCELLED_TRANSACTION_STATUS,
    CONFIRMED_TRANSACTION_STATUS,
    PENDING_TRANSACTION_TTL,
    clone_parsed_message,
    format_active_pending_message,
    get_active_pending_state,
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
from app.modules.parser.amount_parser import extract_amount, parse_amount
from app.modules.parser.date_parser import parse_transaction_date
from app.modules.parser.normalizer import normalize_text
from app.modules.parser.service import ParsedMessage
from app.modules.parser.transaction_text import (
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
)
from app.modules.transactions.repository import (
    calculate_balance,
    detect_category_by_keywords,
    find_category,
    list_transactions,
    sum_category_expense,
    sum_transactions,
    top_expense_category,
)


YES_CONFIRMATION_RE = re.compile(
    r"^\s*(?:ya|iya|y|yes|ok|oke|benar|setuju|simpan|gas|lanjut)(?:\s+(?:simpan|catat))?\s*$",
    re.IGNORECASE,
)
CANCEL_RE = re.compile(r"^\s*(?:batal|cancel|ga jadi|gajadi|jangan(?:\s+simpan)?|hapus)\s*$", re.IGNORECASE)
EDIT_RE = re.compile(r"^\s*(?:edit|ubah|ganti|koreksi|revisi|bukan)\b", re.IGNORECASE)
NATURAL_AMOUNT_EDIT_RE = re.compile(r"\b(?:salah|totalnya|nominalnya)\b", re.IGNORECASE)
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
LIST_ITEM_REQUEST_RE = re.compile(
    r"\b(?:list|daftar|tampilkan|lihat|liat|kasih\s+lihat|kasih\s+liat|buatkan)\b"
    r".*\b(?P<type>pengeluaran|pemasukan)\b"
    r"|\b(?P<type2>pengeluaran|pemasukan)\b.*\b(?:apa\s+saja|apa\s+aja|list|daftar|terbaru)\b",
    re.IGNORECASE,
)
DATE_SORT_REQUEST_RE = re.compile(
    r"\b(?:urutkan|sortir|sort|susun)\b.*\b(?P<order>terlama|terbaru|terkini)\b",
    re.IGNORECASE,
)
PURCHASE_LIST_RE = re.compile(
    r"\b(?:bulan ini|minggu ini|hari ini)\b.*\b(?:beli|belanja|jajan)\b.*\b(?:apa aja|apa saja)\b|"
    r"\b(?:apa aja|apa saja)\b.*\b(?:dibeli|aku beli|saya beli|belanja)\b",
    re.IGNORECASE,
)
TOP_EXPENSE_RE = re.compile(r"\b(?:pengeluaran terbesar|paling gede|terbesar apa|top pengeluaran)\b", re.IGNORECASE)
SAVING_ADVICE_RE = re.compile(
    r"\b(?:saran hemat|tips hemat|cara hemat|hemat minggu ini|saran.*boros|biar.*(?:ga|gak|nggak|tidak)\s+boros|atur uang|rencana hemat|cara ngurangin jajan|target nabung|pengen nabung|mending.*hemat)\b",
    re.IGNORECASE,
)
SAVING_GOAL_RE = re.compile(r"\b(?:target nabung|pengen nabung|mau nabung)\b", re.IGNORECASE)
LIMITED_CASH_RE = re.compile(
    r"\b(?:cuma|tinggal|sisa|punya)\b.*\b(?:sampai|sampe)\b.*\b(?:minggu depan|akhir minggu|minggu ini)\b",
    re.IGNORECASE,
)
CASHFLOW_REASON_RE = re.compile(r"\b(?:kenapa.*(?:saldo|uang).*(?:habis|cepat habis)|saldo.*cepat habis)\b", re.IGNORECASE)
WEEK_COMPARE_RE = re.compile(r"\b(?:bandingkan|dibanding|compare).*(?:minggu ini|minggu lalu)|\bminggu ini.*minggu lalu\b", re.IGNORECASE)
CUTBACK_RE = re.compile(r"\b(?:apa yang harus (?:aku\s+)?dikurangi|apa yang harus (?:aku\s+)?kurangi|kurangi apa|yang perlu dikurangi|pengeluaran.*dikurangi|stop langganan apa)\b", re.IGNORECASE)
EDIT_LAST_CATEGORY_RE = re.compile(
    r"\b(?:ganti|ubah|edit)\s+kategori\s+transaksi\s+terakhir\s+(?:jadi|ke)\s+(?P<category>.+)$",
    re.IGNORECASE,
)
CATEGORY_LOOKUP_RE = re.compile(r"\bkategori\s+(?P<item>.+?)\s+masuk\s+mana\b", re.IGNORECASE)
SPENDING_ANALYSIS_RE = re.compile(
    r"\b(?:aku sering keluar uang (?:buat|untuk) apa|sering keluar uang (?:buat|untuk) apa|evaluasi keuangan|ini mahal gak|catat yang tadi|aku lupa nominalnya|tadi bayar dua kali|salah catat)\b",
    re.IGNORECASE,
)
INCOME_SOURCE_RE = re.compile(
    r"\b(?:pemasukan|pemsukan|income|uang masuk)\b.*\b(?:dari mana|sumber|apa aja|apa saja)\b",
    re.IGNORECASE,
)
SEARCH_TRANSACTION_RE = re.compile(r"^\s*(?:cari|search|temukan)\s+(?P<keyword>.+?)\s*$", re.IGNORECASE)
BUDGET_SET_RE = re.compile(
    r"\b(?:set|atur|pasang|buat(?:kan)?)\s+budget\s+(?P<body>.+)$",
    re.IGNORECASE,
)
BUDGET_LIST_RE = re.compile(r"\b(?:list|daftar|cek|lihat)?\s*budget(?:\s+bulan ini)?\s*$", re.IGNORECASE)
BUDGET_CATEGORY_LIST_RE = re.compile(
    r"\b(?:kategori\s+budget(?:nya)?|budget\s+kategori(?:nya)?)\b.*\b(?:apa|saja|tersedia|bisa|mana)\b"
    r"|\b(?:ada|apa|list|daftar|lihat)\b.*\b(?:kategori\s+budget(?:nya)?|budget\s+kategori(?:nya)?)\b",
    re.IGNORECASE,
)
BUDGET_HELP_RE = re.compile(
    r"\bbudget\b.*\b(?:cara|gimana|bagaimana|format|contoh)\b"
    r"|\b(?:cara|gimana|bagaimana|format|contoh)\b.*\bbudget\b",
    re.IGNORECASE,
)
BUDGET_REMAINING_RE = re.compile(
    r"\bbudget\s+(?P<category>.+?)\s+(?:tinggal|sisa|tersisa|remaining|berapa)\b",
    re.IGNORECASE,
)
BUDGET_WORD_RE = re.compile(r"\b(?:budget|anggaran)\b", re.IGNORECASE)
VISIBILITY_CHECK_RE = re.compile(
    r"\b(?:tidak|ga|gak|nggak|belum)\s+masuk\b.*\b(?:dashboard|list|daftar)\b"
    r"|\b(?:dashboard|list|daftar)\b.*\b(?:tidak|ga|gak|nggak|belum)\s+masuk\b",
    re.IGNORECASE,
)
FINANCE_HEALTH_RE = re.compile(
    r"\b(?:aman|sehat|gimana|bagaimana|kondisi)\b.*\b(?:keuangan|bulan ini|saldo|cashflow)\b|"
    r"\b(?:keuangan|bulan ini|saldo|cashflow|pengeluaran)\b.*\b(?:aman|sehat|gimana|bagaimana|kondisi|sehat)\b",
    re.IGNORECASE,
)
REPLY_STYLE_PREFERENCE_RE = re.compile(
    r"\b(?:gaya bahasa|bahasa|respon)\s+(?P<style>santai|formal|detail|rinci|singkat|pendek)\b",
    re.IGNORECASE,
)
CREATE_CATEGORY_RE = re.compile(
    r"\b(?:buat(?:kan)?|bikin|tambah(?:kan)?|create)\b.*\bkategori\b"
    r"|\bkategori\b.*\b(?:baru|buat(?:kan)?|bikin|tambah(?:kan)?)\b",
    re.IGNORECASE,
)
CATEGORY_SUMMARY_RE = re.compile(
    r"\b(?P<category>makan(?:an)?|kopi|transport|bensin|tagihan|belanja|hiburan|kesehatan|pendidikan|kuliah|kampus|kos)\b.*\b(?:berapa|total|bulan ini|minggu ini|hari ini)\b",
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
CATEGORY_CREATE_MESSAGE_TYPE = "category_create"
PENDING_CATEGORY_CREATE_STATUS = "pending_category_create"
CONFIRMED_CATEGORY_CREATE_STATUS = "confirmed_category_create"
CANCELLED_CATEGORY_CREATE_STATUS = "cancelled_category_create"
EXPIRED_CATEGORY_CREATE_STATUS = "expired_category_create"
TRANSACTION_STATUS_CONFIRMED = "confirmed"


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


@dataclass(frozen=True)
class CategoryCreateRequest:
    name: str
    transaction_type: str
    budget_amount: Decimal | None = None


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

    category_create_result = _handle_category_create_reply(
        db=db,
        user_id=user_id,
        text=text,
        source=source,
    )
    if category_create_result is not None:
        return category_create_result

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

    active_pending = get_active_pending_state(db, user_id=user_id)
    if active_pending is not None:
        return _active_pending_result(
            pending=active_pending,
            text=text,
            source=source,
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

    if _needs_ambiguous_amount_confirmation(text, parse_result):
        pending_parse = clone_parsed_message(
            parse_result,
            amount=None,
            need_confirmation=True,
            reasons=[*parse_result.reasons, "ambiguous_small_amount"],
        )
        store_pending_transaction(
            db,
            user_id=user_id,
            platform=_platform_from_source(source),
            raw_message=text,
            parse_result=pending_parse,
        )
        return TextTransactionResult(
            status="needs_confirmation",
            reply_text="Nominalnya belum jelas. Maksudnya 18 ribu? Balas nominal lengkap, contoh: 18 ribu.",
            parse_result=pending_parse,
            error_message="ambiguous_small_amount",
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

    # Try keyword-based auto-categorization if category is fallback
    category_name = parse_result.category
    if (
        parse_result.description
        and category_name in {"Lainnya", None}
    ):
        keyword_cat = detect_category_by_keywords(
            db,
            user_id,
            parse_result.description,
            transaction_type=parse_result.type,
        )
        if keyword_cat is not None:
            category_name = keyword_cat.name

    category = find_category(
        db=db,
        category_name=category_name,
        transaction_type=parse_result.type,
        user_id=user_id,
    )
    transaction = Transaction(
        user_id=user_id,
        type=parse_result.type,
        amount=parse_result.amount,
        category_id=category.id if category else None,
        description=parse_result.description,
        transaction_date=parse_result.transaction_date or date.today(),
        source=parse_result.source,
        status=TRANSACTION_STATUS_CONFIRMED,
    )
    try:
        db.add(transaction)
        db.flush()
        if pending_log is not None:
            mark_pending_status(
                db,
                pending_log=pending_log,
                status=CONFIRMED_TRANSACTION_STATUS,
            )
        db.commit()
        db.refresh(transaction)
    except SQLAlchemyError as exc:
        db.rollback()
        return TextTransactionResult(
            status="save_failed",
            reply_text="Maaf, transaksi belum berhasil kusimpan. Coba kirim ulang sebentar lagi.",
            parse_result=parse_result,
            error_message=str(exc),
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

    active_pending = get_active_pending_state(db, user_id=user_id, exclude_kinds={"reset"})
    if active_pending is not None:
        return _active_pending_result(pending=active_pending, text=text, source=source)

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


def _handle_category_create_reply(
    *,
    db: Session,
    user_id: int,
    text: str,
    source: str,
) -> TextTransactionResult | None:
    normalized = normalize_text(text)
    pending = _get_pending_category_create(db, user_id=user_id)
    if pending is not None:
        payload = pending.parsed_result or {}
        name = str(payload.get("name") or "").strip()
        transaction_type = str(payload.get("type") or "expense")
        budget_amount = _payload_decimal(payload.get("budget_amount"))
        replacement = _parse_category_create_request(text)
        if replacement is not None:
            name = replacement.name
            transaction_type = replacement.transaction_type
            budget_amount = replacement.budget_amount
            pending.raw_message = text
            pending.parsed_result = {
                "kind": "category_create",
                "name": name,
                "type": transaction_type,
                "budget_amount": str(budget_amount) if budget_amount is not None else None,
            }
            db.commit()
            return TextTransactionResult(
                status="category_create_needs_confirmation",
                reply_text=_format_category_create_pending_reply(
                    name=name,
                    transaction_type=transaction_type,
                    budget_amount=budget_amount,
                ),
                parse_result=_synthetic_parse_result(
                    text=text,
                    source=source,
                    intent=INTENT_CREATE_CATEGORY,
                ),
            )

        if CANCEL_RE.match(normalized):
            pending.status = CANCELLED_CATEGORY_CREATE_STATUS
            db.commit()
            return TextTransactionResult(
                status="category_create_cancelled",
                reply_text=f"Oke, kategori {name} batal dibuat.",
                parse_result=_synthetic_parse_result(
                    text=text,
                    source=source,
                    intent=INTENT_CREATE_CATEGORY,
                ),
            )

        if YES_CONFIRMATION_RE.match(normalized):
            category = find_category(
                db=db,
                category_name=name,
                transaction_type=transaction_type,
                user_id=user_id,
            )
            if category is None or category.name.lower() != name.lower():
                category = Category(name=name, type=transaction_type, user_id=user_id)
                db.add(category)
                db.flush()
            if budget_amount is not None and transaction_type == "expense":
                upsert_category_budget(
                    db,
                    user_id=user_id,
                    category=category,
                    monthly_limit=budget_amount,
                )
            pending.status = CONFIRMED_CATEGORY_CREATE_STATUS
            db.commit()
            return TextTransactionResult(
                status="category_created",
                reply_text=_format_category_created_reply(
                    name=name,
                    budget_amount=budget_amount if transaction_type == "expense" else None,
                ),
                parse_result=_synthetic_parse_result(
                    text=text,
                    source=source,
                    intent=INTENT_CREATE_CATEGORY,
                ),
            )

        return None

    request = _parse_category_create_request(text)
    if request is None:
        return None

    name = request.name
    transaction_type = request.transaction_type
    budget_amount = request.budget_amount
    active_pending = get_active_pending_state(db, user_id=user_id, exclude_kinds={"category"})
    if active_pending is not None:
        return _active_pending_result(pending=active_pending, text=text, source=source)

    existing = find_category(
        db=db,
        category_name=name,
        transaction_type=transaction_type,
        user_id=user_id,
    )
    if existing is not None and existing.name.lower() == name.lower():
        return TextTransactionResult(
            status="category_exists",
            reply_text=f"Kategori {existing.name} sudah ada.",
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent=INTENT_CREATE_CATEGORY,
            ),
        )

    db.add(
        BotLog(
            user_id=user_id,
            platform=_platform_from_source(source),
            message_type=CATEGORY_CREATE_MESSAGE_TYPE,
            raw_message=text,
            parsed_result={
                "kind": "category_create",
                "name": name,
                "type": transaction_type,
                "budget_amount": str(budget_amount) if budget_amount is not None else None,
            },
            status=PENDING_CATEGORY_CREATE_STATUS,
        )
    )
    db.commit()
    return TextTransactionResult(
        status="category_create_needs_confirmation",
        reply_text=_format_category_create_pending_reply(
            name=name,
            transaction_type=transaction_type,
            budget_amount=budget_amount,
        ),
        parse_result=_synthetic_parse_result(
            text=text,
            source=source,
            intent=INTENT_CREATE_CATEGORY,
        ),
    )


def _get_pending_category_create(db: Session, *, user_id: int) -> BotLog | None:
    pending = db.scalar(
        select(BotLog)
        .where(
            BotLog.user_id == user_id,
            BotLog.message_type == CATEGORY_CREATE_MESSAGE_TYPE,
            BotLog.status == PENDING_CATEGORY_CREATE_STATUS,
        )
        .order_by(BotLog.created_at.desc(), BotLog.id.desc())
    )
    if pending is None:
        return None
    created_at = pending.created_at if pending.created_at.tzinfo else pending.created_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - created_at > PENDING_TRANSACTION_TTL:
        pending.status = EXPIRED_CATEGORY_CREATE_STATUS
        db.flush()
        return None
    return pending


def _parse_category_create_request(text: str) -> CategoryCreateRequest | None:
    if not CREATE_CATEGORY_RE.search(text):
        return None
    normalized = normalize_text(text)
    match = re.search(
        r"\bkategori(?:\s+baru)?(?:\s+untuk)?\s+(?P<name>.+)$",
        normalized,
        re.IGNORECASE,
    )
    if not match:
        match = re.search(
            r"\b(?:buatkan|buat|bikin|tambahkan|tambah|create)\s+(?:saya\s+)?"
            r"kategori(?:\s+baru)?(?:\s+untuk)?\s+(?P<name>.+)$",
            normalized,
            re.IGNORECASE,
        )
    if not match:
        return None

    raw_name = match.group("name")
    amount_match = extract_amount(raw_name)
    budget_amount = amount_match.value if amount_match is not None else None
    if amount_match is not None:
        raw_name = raw_name[: amount_match.start] + raw_name[amount_match.end :]

    raw_name = re.sub(
        r"\b(?:set\s+budget(?:nya)?|budget(?:nya)?|anggaran|pengeluaran|pemasukan|income|expense|untuk|saya|dong|ya|dan|set|atur|pasang)\b",
        " ",
        raw_name,
        flags=re.IGNORECASE,
    )
    name = re.sub(r"\s+", " ", raw_name).strip(" -,.")
    if len(name) < 3:
        return None
    transaction_type = "income" if re.search(r"\b(?:pemasukan|income)\b", normalized) else "expense"
    return CategoryCreateRequest(
        name=name.title(),
        transaction_type=transaction_type,
        budget_amount=budget_amount,
    )


def _payload_decimal(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _format_category_create_pending_reply(
    *,
    name: str,
    transaction_type: str,
    budget_amount: Decimal | None,
) -> str:
    label = "pengeluaran" if transaction_type == "expense" else "pemasukan"
    budget_part = (
        f" dan set budget {format_rupiah(budget_amount)}"
        if budget_amount is not None and transaction_type == "expense"
        else ""
    )
    return f"Siap, aku siap buat kategori {label}: {name}{budget_part}. Balas YA untuk simpan, atau batal."


def _format_category_created_reply(*, name: str, budget_amount: Decimal | None) -> str:
    if budget_amount is None:
        return f"Siap, kategori {name} sudah tersimpan."
    return f"Kategori {name} dibuat. Budget {format_rupiah(budget_amount)} juga sudah diset."


def _active_pending_result(
    *,
    pending: Any,
    text: str,
    source: str,
) -> TextTransactionResult:
    return TextTransactionResult(
        status="active_pending",
        reply_text=format_active_pending_message(pending),
        parse_result=_synthetic_parse_result(
            text=text,
            source=source,
            intent="active_pending",
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
    query = select(func.count(Transaction.id)).where(
        Transaction.user_id == user_id,
        Transaction.status == TRANSACTION_STATUS_CONFIRMED,
    )
    if reset_type in {"expense", "income"}:
        query = query.where(Transaction.type == reset_type)
    return int(db.scalar(query) or 0)


def _execute_transaction_reset(db: Session, *, user_id: int, reset_type: str) -> int:
    query = select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.status == TRANSACTION_STATUS_CONFIRMED,
    )
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
        if EDIT_LAST_CATEGORY_RE.search(normalized):
            return None
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

    if (
        EDIT_RE.match(normalized)
        or NATURAL_AMOUNT_EDIT_RE.search(normalized)
        or _looks_like_missing_amount_reply(parse_result, normalized)
    ):
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
    if _is_amount_without_context(normalized):
        return TextTransactionResult(
            status="needs_confirmation",
            reply_text="Nominalnya buat transaksi apa? Contoh: beli kopi 15k atau pemasukan 15k.",
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="needs_confirmation",
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
    budget_result = _handle_budget_message(
        db=db,
        user_id=user_id,
        text=normalized,
        source=source,
    )
    if budget_result is not None:
        return budget_result
    edit_last_result = _handle_edit_last_category_message(
        db=db,
        user_id=user_id,
        text=normalized,
        source=source,
    )
    if edit_last_result is not None:
        return edit_last_result
    category_lookup = CATEGORY_LOOKUP_RE.search(normalized)
    if category_lookup:
        item = category_lookup.group("item")
        category_name = _category_name_from_alias(item)
        return TextTransactionResult(
            status="category_lookup",
            reply_text=f"{item.strip().title()} paling cocok masuk kategori {category_name}.",
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="category_lookup",
            ),
        )
    if VISIBILITY_CHECK_RE.search(normalized):
        return TextTransactionResult(
            status="transaction_visibility_check",
            reply_text=_format_visibility_check_response(db, user_id, normalized),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="transaction_visibility_check",
            ),
        )
    date_sort_match = DATE_SORT_REQUEST_RE.search(normalized)
    if date_sort_match and ("pengeluaran" in normalized or "list" in normalized):
        order = date_sort_match.group("order").lower()
        return TextTransactionResult(
            status="sorted_expense",
            reply_text=_format_sorted_expense_response(
                db,
                user_id,
                period=_detect_period_from_text(normalized) or "month",
                sort_order="date_asc" if order == "terlama" else "date_desc",
                limit=50 if _wants_all_items(normalized) else None,
            ),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent=INTENT_SORTED_EXPENSE,
            ),
        )
    list_match = LIST_ITEM_REQUEST_RE.search(normalized)
    if list_match:
        txn_word = (list_match.group("type") or list_match.group("type2")).lower()
        transaction_type = "income" if txn_word == "pemasukan" else "expense"
        return TextTransactionResult(
            status=INTENT_LIST_INCOME if transaction_type == "income" else INTENT_LIST_EXPENSE,
            reply_text=_format_transaction_list_response(
                db,
                user_id,
                transaction_type=transaction_type,
                period=_detect_period_from_text(normalized),
                limit=50 if _wants_all_items(normalized) else None,
            ),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent=INTENT_LIST_INCOME if transaction_type == "income" else INTENT_LIST_EXPENSE,
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
    if SAVING_GOAL_RE.search(normalized):
        return TextTransactionResult(
            status="saving_goal",
            reply_text=_format_saving_goal_response(normalized),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="saving_goal",
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
    if LIMITED_CASH_RE.search(normalized) and parse_amount(normalized) is not None:
        return TextTransactionResult(
            status="limited_cash_plan",
            reply_text=_format_limited_cash_plan_response(normalized),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="limited_cash_plan",
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
    if SPENDING_ANALYSIS_RE.search(normalized):
        return _handle_contextual_finance_message(
            db=db,
            user_id=user_id,
            text=text,
            normalized=normalized,
            source=source,
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


def _is_amount_without_context(text: str) -> bool:
    amount_match = extract_amount(text)
    if amount_match is None:
        return False
    rest = (text[: amount_match.start] + text[amount_match.end :]).strip(" -,.?")
    return not re.search(r"[a-zA-Z\u00c0-\u024f]{2,}", rest)


def _needs_ambiguous_amount_confirmation(text: str, parse_result: ParsedMessage) -> bool:
    if parse_result.intent != INTENT_ADD_TRANSACTION or parse_result.amount is None:
        return False
    if parse_result.amount >= Decimal("1000"):
        return False
    return not re.search(r"\b(?:rp|rb|ribu|k|jt|juta)\b|[.,]\d{3}", text.lower())


def _handle_edit_last_category_message(
    *,
    db: Session,
    user_id: int,
    text: str,
    source: str,
) -> TextTransactionResult | None:
    match = EDIT_LAST_CATEGORY_RE.search(text)
    if not match:
        return None

    category_name = _category_name_from_alias(match.group("category"))
    category = find_category(
        db=db,
        category_name=category_name,
        transaction_type="expense",
        user_id=user_id,
    )
    if category is None:
        return TextTransactionResult(
            status="edit_last_transaction_category_not_found",
            reply_text=f"Kategori {category_name} belum ada.",
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="edit_last_transaction",
            ),
        )

    transaction = db.scalar(
        select(Transaction)
        .where(
            Transaction.user_id == user_id,
            Transaction.status == TRANSACTION_STATUS_CONFIRMED,
        )
        .order_by(Transaction.created_at.desc(), Transaction.id.desc())
    )
    if transaction is None:
        return TextTransactionResult(
            status="edit_last_transaction_not_found",
            reply_text="Belum ada transaksi yang bisa diedit.",
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="edit_last_transaction",
            ),
        )

    transaction.category_id = category.id
    db.commit()
    return TextTransactionResult(
        status="edit_last_transaction",
        reply_text=f"Siap, kategori transaksi terakhir kuganti jadi {category.name}.",
        parse_result=_synthetic_parse_result(
            text=text,
            source=source,
            intent="edit_last_transaction",
        ),
        transaction_id=transaction.id,
    )


def _handle_contextual_finance_message(
    *,
    db: Session,
    user_id: int,
    text: str,
    normalized: str,
    source: str,
) -> TextTransactionResult:
    if re.search(r"\b(?:catat yang tadi|aku lupa nominalnya|salah catat)\b", normalized):
        status = "needs_context"
    elif "tadi bayar dua kali" in normalized:
        status = "duplicate_check"
    else:
        status = "finance_chat"
    return TextTransactionResult(
        status=status,
        reply_text=_format_contextual_finance_response(db, user_id, normalized),
        parse_result=_synthetic_parse_result(
            text=text,
            source=source,
            intent=status,
        ),
    )


def _format_contextual_finance_response(db: Session, user_id: int, text: str) -> str:
    if re.search(r"\b(?:catat yang tadi|aku lupa nominalnya)\b", text):
        return "Aku butuh detailnya dulu. Kirim seperti: beli kopi 18 ribu atau pemasukan 100rb."
    if re.search(r"\b(?:tadi bayar dua kali|salah catat)\b", text):
        return "Kalau transaksi terakhir salah, kirim: ganti kategori transaksi terakhir jadi makanan, atau kosongkan pengeluaran kalau mau reset."
    if "mahal" in text:
        return "Bisa aku bantu nilai kalau ada nominal dan konteksnya. Contoh: beli kopi 35 ribu, mahal gak?"
    return _format_spending_check_response(db, user_id, text=text)


def _format_saving_goal_response(text: str) -> str:
    amount = parse_amount(text)
    if amount is None:
        return "Bisa. Sebutkan targetnya, contoh: aku pengen nabung 500rb bulan ini."
    days_left = max(1, (date.today().replace(day=28) - date.today()).days + 4)
    daily = amount / Decimal(days_left)
    return (
        f"Bisa. Target tabungan {format_rupiah(amount)} bulan ini berarti sekitar "
        f"{format_rupiah(daily)} per hari. Sisihkan dulu setelah pemasukan, baru atur jajan dari sisanya."
    )


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
        "kuliah": "Pendidikan",
        "kampus": "Pendidikan",
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
            limit=parse_result.limit,
        )
    if parse_result.intent == INTENT_LIST_INCOME:
        return _format_transaction_list_response(
            db,
            user_id,
            transaction_type="income",
            period=parse_result.period,
            limit=parse_result.limit,
        )
    if parse_result.intent == INTENT_SORTED_EXPENSE:
        return _format_sorted_expense_response(
            db,
            user_id,
            period=parse_result.period,
            sort_order=parse_result.sort_order or "desc",
            limit=parse_result.limit,
        )
    if parse_result.intent == INTENT_CATEGORY_DETAIL:
        return _format_category_detail_response(
            db,
            user_id,
            category_name=parse_result.category_filter or "Lainnya",
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
    if parse_result.intent == INTENT_CREATE_CATEGORY:
        return "Sebutkan nama kategorinya. Contoh: buat kategori Tugas Kuliah."
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
    return format_saved_transaction_template(
        transaction,
        category,
        style=_reply_style(db, user_id),
        balance_after=balance_after,
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
    limit: int | None = None,
) -> str:
    effective_limit = min(max(limit or 10, 1), 50)
    start_date, end_date = _period_bounds(period)
    transactions = list_transactions(
        db,
        user_id,
        transaction_type=transaction_type,
        start_date=start_date,
        end_date=end_date,
        limit=effective_limit,
        newest_by_created=True,
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
    displayed_total = sum(item.amount for item in transactions)
    period_total = sum_transactions(
        db,
        user_id,
        transaction_type=transaction_type,
        start_date=start_date,
        end_date=end_date,
    )
    total_count = _count_transactions(
        db,
        user_id=user_id,
        transaction_type=transaction_type,
        start_date=start_date,
        end_date=end_date,
    )
    shown_line = (
        f"\nMenampilkan {len(transactions)} dari {total_count} transaksi."
        if total_count > len(transactions)
        else ""
    )
    total_line = (
        f"\n\nTotal ditampilkan: {format_rupiah(displayed_total)}\n"
        f"Total {_period_total_label(period)}: {format_rupiah(period_total)}"
        f"{shown_line}"
    )
    return (
        f"Aku cek, {name}. List {label} {_format_period(period)} kamu:\n\n"
        + "\n".join(lines)
        + total_line
    )


def _format_sorted_expense_response(
    db: Session,
    user_id: int,
    *,
    period: str | None,
    sort_order: str = "desc",
    limit: int | None = None,
) -> str:
    start_date, end_date = _period_bounds(period or "month")
    effective_limit = min(max(limit or 10, 1), 50)
    if sort_order in {"date_asc", "date_desc"}:
        order_by = (
            (Transaction.transaction_date.asc(), Transaction.id.asc())
            if sort_order == "date_asc"
            else (Transaction.transaction_date.desc(), Transaction.id.desc())
        )
        transactions = list(
            db.scalars(
                select(Transaction)
                .where(
                    Transaction.user_id == user_id,
                    Transaction.type == "expense",
                    Transaction.status == TRANSACTION_STATUS_CONFIRMED,
                    Transaction.transaction_date >= start_date,
                    Transaction.transaction_date <= end_date,
                )
                .order_by(*order_by)
                .limit(effective_limit)
            )
        )
    else:
        transactions = list_transactions(
            db,
            user_id,
            transaction_type="expense",
            start_date=start_date,
            end_date=end_date,
            limit=effective_limit,
            sort_by_amount=True,
            sort_order=sort_order,
        )
    name = _user_first_name(db, user_id)
    if not transactions:
        return f"Belum ada pengeluaran {_format_period(period or 'month')}, {name}."

    order_label = {
        "asc": "terkecil ke terbesar",
        "date_asc": "terlama ke terbaru",
        "date_desc": "terbaru ke terlama",
    }.get(sort_order, "terbesar ke terkecil")
    lines = [
        f"{index}. {format_rupiah(item.amount)} - "
        f"{item.category.name if item.category else 'Tanpa kategori'}"
        f"{f' - {item.description}' if item.description else ''}"
        f" ({item.transaction_date.isoformat()})"
        for index, item in enumerate(transactions, start=1)
    ]
    displayed_total = sum(item.amount for item in transactions)
    period_total = sum_transactions(
        db,
        user_id,
        transaction_type="expense",
        start_date=start_date,
        end_date=end_date,
    )
    return (
        f"Pengeluaran {_format_period(period or 'month')} ({order_label}), {name}:\n\n"
        + "\n".join(lines)
        + f"\n\nTotal ditampilkan: {format_rupiah(displayed_total)}\n"
        + f"Total {_period_total_label(period or 'month')}: {format_rupiah(period_total)}"
    )


def _format_category_detail_response(
    db: Session,
    user_id: int,
    *,
    category_name: str,
    period: str | None,
) -> str:
    start_date, end_date = _period_bounds(period or "month")
    transactions = list_transactions(
        db,
        user_id,
        transaction_type="expense",
        start_date=start_date,
        end_date=end_date,
        limit=10,
        newest_by_created=True,
        category_name=category_name,
    )
    name = _user_first_name(db, user_id)
    if not transactions:
        return f"Belum ada transaksi {category_name} {_format_period(period or 'month')}, {name}."

    lines = [
        f"{index}. {item.transaction_date.isoformat()} - "
        f"{format_rupiah(item.amount)}"
        f"{f' - {item.description}' if item.description else ''}"
        for index, item in enumerate(transactions, start=1)
    ]
    total = sum(item.amount for item in transactions)
    return (
        f"Rincian {category_name} {_format_period(period or 'month')}, {name}:\n\n"
        + "\n".join(lines)
        + f"\n\nTotal {category_name}: {format_rupiah(total)}"
    )


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
    month_start = today.replace(day=1)
    top_categories = _top_expense_categories(db, user_id, start_date=month_start, end_date=today)
    month_income = sum_transactions(
        db,
        user_id,
        transaction_type="income",
        start_date=month_start,
        end_date=today,
    )
    month_expense = sum_transactions(
        db,
        user_id,
        transaction_type="expense",
        start_date=month_start,
        end_date=today,
    )
    if not top_categories:
        return "Belum ada pengeluaran bulan ini. Mulai catat transaksi dulu biar sarannya akurat."

    remaining_days = max((today.replace(day=28) + timedelta(days=4)).replace(day=1) - today, timedelta(days=1)).days
    daily_limit = max((month_income - month_expense) / Decimal(remaining_days), Decimal("0"))
    category_name, total = top_categories[0]
    cutbacks = ", ".join(name for name, _total in top_categories[:2])
    return (
        f"Fokus hemat bulan ini:\n"
        f"1. Rem {category_name}: sudah {format_rupiah(total)}.\n"
        f"2. Batas aman harian sampai akhir bulan: {format_rupiah(daily_limit)}.\n"
        f"3. Kurangi dulu: {cutbacks}."
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
                Transaction.status == TRANSACTION_STATUS_CONFIRMED,
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


def _format_visibility_check_response(db: Session, user_id: int, text: str) -> str:
    limit = 50 if _wants_all_items(text) else 10
    transactions = list_transactions(db, user_id, limit=limit, newest_by_created=True)
    if not transactions:
        return "Aku cek database akun ini: belum ada transaksi confirmed yang bisa ditampilkan."

    lines = [
        f"{index}. #{item.id} {item.transaction_date.isoformat()} - "
        f"{'Pemasukan' if item.type == 'income' else 'Pengeluaran'} "
        f"{format_rupiah(item.amount)} - "
        f"{item.category.name if item.category else 'Tanpa kategori'}"
        f"{f' - {item.description}' if item.description else ''}"
        for index, item in enumerate(transactions, start=1)
    ]
    return (
        "Aku cek dari database akun ini. Transaksi confirmed terbaru:\n\n"
        + "\n".join(lines)
        + "\n\nKalau belum tampil di dashboard, cek akun login, filter tanggal/tipe, lalu refresh."
    )


def _handle_budget_message(
    *,
    db: Session,
    user_id: int,
    text: str,
    source: str,
) -> TextTransactionResult | None:
    has_budget_word = BUDGET_WORD_RE.search(text) is not None

    if BUDGET_CATEGORY_LIST_RE.search(text):
        return TextTransactionResult(
            status="budget_category_list",
            reply_text=_format_budget_category_options(db, user_id),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="budget_category_list",
            ),
        )

    if BUDGET_HELP_RE.search(text) and extract_amount(text) is None:
        return _budget_help_result(text=text, source=source)

    set_match = BUDGET_SET_RE.search(text)
    if set_match:
        active_pending = get_active_pending_state(db, user_id=user_id)
        if active_pending is not None:
            return _active_pending_result(pending=active_pending, text=text, source=source)
        return _handle_set_budget_message(
            db=db,
            user_id=user_id,
            text=text,
            source=source,
            body=set_match.group("body"),
        )

    remaining_match = BUDGET_REMAINING_RE.search(text)
    if remaining_match:
        return _handle_budget_remaining_message(
            db=db,
            user_id=user_id,
            text=text,
            source=source,
            category_text=remaining_match.group("category"),
        )

    if BUDGET_LIST_RE.fullmatch(text):
        return TextTransactionResult(
            status="budget_list",
            reply_text=_format_budget_list_response(db, user_id),
            parse_result=_synthetic_parse_result(
                text=text,
                source=source,
                intent="budget_list",
            ),
        )
    if has_budget_word:
        return _budget_help_result(text=text, source=source)
    return None


def _handle_set_budget_message(
    *,
    db: Session,
    user_id: int,
    text: str,
    source: str,
    body: str,
) -> TextTransactionResult:
    amount_match = extract_amount(body)
    if amount_match is None:
        if BUDGET_HELP_RE.search(text):
            return _budget_help_result(text=text, source=source)
        return TextTransactionResult(
            status="budget_invalid",
            reply_text=_budget_help_text("Nominal budget belum terbaca."),
            parse_result=_synthetic_parse_result(text=text, source=source, intent="budget_invalid"),
        )

    category_name = _clean_budget_category_name(body[:amount_match.start] + body[amount_match.end:])
    category = _find_budget_category(db, user_id=user_id, category_text=category_name)
    if category is None:
        return TextTransactionResult(
            status="budget_category_not_found",
            reply_text=_budget_help_text(f"Kategori '{category_name or '-'}' belum ketemu."),
            parse_result=_synthetic_parse_result(text=text, source=source, intent="budget_category_not_found"),
        )

    budget = upsert_category_budget(
        db,
        user_id=user_id,
        category=category,
        monthly_limit=amount_match.value,
    )
    db.commit()
    db.refresh(budget)
    budget_state = get_budget_for_category(db, user_id, category)
    item = budget_state[2] if budget_state else None
    remaining = item.remaining if item else amount_match.value
    reply = (
        f"Budget {category.name}: {format_rupiah(amount_match.value)}.\n"
        f"Terpakai {format_rupiah(item.spent if item else Decimal('0'))}. "
        f"Sisa {format_rupiah(remaining)}."
    )
    return TextTransactionResult(
        status="budget_saved",
        reply_text=reply,
        parse_result=_synthetic_parse_result(text=text, source=source, intent="budget_saved"),
    )


def _handle_budget_remaining_message(
    *,
    db: Session,
    user_id: int,
    text: str,
    source: str,
    category_text: str,
) -> TextTransactionResult:
    category = _find_budget_category(db, user_id=user_id, category_text=category_text)
    if category is None:
        reply = f"Kategori '{category_text.strip()}' belum ketemu. Coba: budget makan tinggal berapa?"
    else:
        budget_state = get_budget_for_category(db, user_id, category)
        if budget_state is None:
            reply = f"Budget {category.name} belum diset. Contoh: set budget {category.name.lower()} 600rb."
        else:
            _period_start, _period_end, item = budget_state
            reply = (
                f"Budget {item.category_name}: {format_rupiah(item.monthly_limit)}.\n"
                f"Terpakai {format_rupiah(item.spent)}. "
                f"Sisa {format_rupiah(item.remaining)}."
            )
    return TextTransactionResult(
        status="budget_remaining",
        reply_text=reply,
        parse_result=_synthetic_parse_result(text=text, source=source, intent="budget_remaining"),
    )


def _format_budget_list_response(db: Session, user_id: int) -> str:
    overview = get_budget_overview(db, user_id)
    if not overview.items:
        return "Belum ada budget. Contoh: set budget makan 600rb."

    lines = [
        f"{index}. {item.category_name}: {format_rupiah(item.monthly_limit)} - "
        f"terpakai {format_rupiah(item.spent)} - sisa {format_rupiah(item.remaining)}"
        for index, item in enumerate(overview.items, start=1)
    ]
    fallback_reply = (
        "Budget bulan ini:\n\n"
        + "\n".join(lines)
        + f"\n\nTotal budget: {format_rupiah(overview.total_budgeted)}\n"
        + f"Sisa total: {format_rupiah(overview.total_remaining)}"
    )
    return fallback_reply


def _budget_help_result(*, text: str, source: str) -> TextTransactionResult:
    return TextTransactionResult(
        status="budget_help",
        reply_text=_budget_help_text(),
        parse_result=_synthetic_parse_result(text=text, source=source, intent="budget_help"),
    )


def _budget_help_text(prefix: str | None = None) -> str:
    lines = [
        "Format budget:",
        "- set budget kuliah 500rb",
        "- budget kuliah tinggal berapa?",
        "- list budget",
    ]
    return "\n".join(([prefix, ""] if prefix else []) + lines)


def _format_budget_category_options(db: Session, user_id: int) -> str:
    categories = db.scalars(
        select(Category)
        .where(
            Category.is_active.is_(True),
            Category.type.in_(("expense", "both")),
            ((Category.user_id == user_id) | Category.user_id.is_(None)),
        )
        .order_by(Category.user_id.is_(None).asc(), Category.name.asc(), Category.id.asc())
    )
    names: list[str] = []
    seen: set[str] = set()
    for category in categories:
        key = category.name.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(category.name)

    if not names:
        return "Belum ada kategori pengeluaran yang bisa diberi budget."
    return (
        "Kategori yang bisa kamu kasih budget:\n"
        + ", ".join(names)
        + "\n\nBudget yang sudah diset bisa dicek dengan: list budget"
    )


def _find_budget_category(db: Session, *, user_id: int, category_text: str) -> Category | None:
    cleaned = _clean_budget_category_name(category_text)
    if not cleaned:
        return None

    exact = find_visible_expense_category_by_name(db, user_id=user_id, name=cleaned)
    if exact is not None:
        return exact

    normalized = cleaned.lower()
    if any(keyword in normalized for keyword in ("kuliah", "kampus")):
        user_kuliah = find_visible_expense_category_by_name(db, user_id=user_id, name="Kuliah")
        if user_kuliah is not None:
            return user_kuliah

    alias = _category_name_from_alias(cleaned)
    return find_visible_expense_category_by_name(db, user_id=user_id, name=alias)


def _clean_budget_category_name(value: str) -> str:
    cleaned = re.sub(r"\b(?:kategori|category|pengeluaran|bulanan)\b", " ", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip(" -,.")


def _format_limited_cash_plan_response(text: str) -> str:
    amount = parse_amount(text) or Decimal("0")
    days = 7 if "minggu depan" in text else max(1, 7 - date.today().weekday())
    daily_limit = amount / Decimal(days)
    return (
        f"Dengan {format_rupiah(amount)} sampai {days} hari ke depan, batas aman sekitar "
        f"{format_rupiah(daily_limit)} per hari.\n"
        "Prioritas: makan, transport, dan tagihan wajib dulu.\n"
        "Tahan dulu: jajan, belanja, top up, dan nongkrong sampai ada pemasukan lagi."
    )


def _count_transactions(
    db: Session,
    *,
    user_id: int,
    transaction_type: str,
    start_date: date | None,
    end_date: date | None,
) -> int:
    query = select(func.count(Transaction.id)).where(
        Transaction.user_id == user_id,
        Transaction.type == transaction_type,
        Transaction.status == TRANSACTION_STATUS_CONFIRMED,
    )
    if start_date is not None:
        query = query.where(Transaction.transaction_date >= start_date)
    if end_date is not None:
        query = query.where(Transaction.transaction_date <= end_date)
    return int(db.scalar(query) or 0)


def _top_expense_categories(
    db: Session,
    user_id: int,
    *,
    start_date: date,
    end_date: date,
    limit: int = 2,
) -> list[tuple[str, Decimal]]:
    rows = db.execute(
        select(Category.name, func.coalesce(func.sum(Transaction.amount), 0))
        .join(Category, Transaction.category_id == Category.id, isouter=True)
        .where(
            Transaction.user_id == user_id,
            Transaction.type == "expense",
            Transaction.status == TRANSACTION_STATUS_CONFIRMED,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date <= end_date,
        )
        .group_by(Category.name)
        .order_by(func.coalesce(func.sum(Transaction.amount), 0).desc())
        .limit(limit)
    )
    return [(name or "Tanpa kategori", Decimal(str(total or 0))) for name, total in rows]


def _detect_period_from_text(text: str) -> str | None:
    if "hari ini" in text:
        return "day"
    if "kemarin" in text:
        return "yesterday"
    if "minggu ini" in text:
        return "week"
    if "bulan ini" in text:
        return "month"
    return None


def _wants_all_items(text: str) -> bool:
    return bool(re.search(r"\b(?:semua|seluruh|full)\b", text))


def _period_total_label(period: str | None) -> str:
    labels = {
        "day": "hari ini",
        "week": "minggu ini",
        "month": "bulan ini",
        "yesterday": "kemarin",
    }
    return labels.get(period or "", "semua transaksi")


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
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    if period == "month":
        return today.replace(day=1), today
    return None, None


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
    if any(keyword in normalized for keyword in ["makan", "makanan", "kopi"]):
        return "Makanan"
    if any(keyword in normalized for keyword in ["transport", "transportasi", "bensin", "gojek", "grab"]):
        return "Transportasi"
    if any(keyword in normalized for keyword in ["kos", "tagihan", "wifi", "pulsa", "paket data"]):
        return "Tagihan"
    if any(keyword in normalized for keyword in ["kuliah", "kampus", "pendidikan", "print", "jurnal", "fotokopi", "tugas", "buku"]):
        return "Pendidikan"
    if normalized in {"nongkrong", "hiburan"}:
        return "Hiburan"
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
