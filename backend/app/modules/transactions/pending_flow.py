"""Focused flow extracted from transaction message orchestration."""

from datetime import datetime, timezone

from app.models import BotLog, Receipt
from app.modules.bot.conversation_state import (
    CANCELLED_TRANSACTION_STATUS,
    PENDING_TRANSACTION_TTL,
    get_pending_transaction,
    update_pending_transaction,
)
from app.modules.bot.response_templates import (
    format_cancelled_response,
    format_no_pending_response,
)
from app.modules.budgets.service import upsert_category_budget
from app.modules.parser.date_parser import parse_transaction_date
from app.modules.transactions.transaction_flow import (
    CANCEL_RE,
    CANCELLED_CATEGORY_CREATE_STATUS,
    CANCELLED_RESET_STATUS,
    CATEGORY_CREATE_MESSAGE_TYPE,
    CONFIRMED_CATEGORY_CREATE_STATUS,
    CONFIRMED_RESET_STATUS,
    CREATE_CATEGORY_RE,
    EDIT_LAST_CATEGORY_RE,
    EDIT_RE,
    EXPIRED_CATEGORY_CREATE_STATUS,
    EXPIRED_RESET_STATUS,
    INTENT_ADD_TRANSACTION,
    INTENT_CREATE_CATEGORY,
    NATURAL_AMOUNT_EDIT_RE,
    PENDING_CATEGORY_CREATE_STATUS,
    PENDING_RESET_STATUS,
    RESET_CONFIRM_RE,
    RESET_MESSAGE_TYPE,
    RESET_REQUEST_RE,
    TRANSACTION_STATUS_CONFIRMED,
    YES_CONFIRMATION_RE,
    Category,
    Decimal,
    ParsedMessage,
    Session,
    TextTransactionResult,
    Transaction,
    _active_pending_result,
    _format_confirmation_request,
    _platform_from_source,
    _save_transaction_from_parse_result,
    _synthetic_parse_result,
    clone_parsed_message,
    dataclass,
    date,
    extract_amount,
    find_category,
    format_rupiah,
    func,
    get_active_pending_state,
    mark_pending_status,
    normalize_text,
    parse_amount,
    re,
    select,
)


@dataclass(frozen=True)
class CategoryCreateRequest:
    name: str
    transaction_type: str
    budget_amount: Decimal | None = None


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
