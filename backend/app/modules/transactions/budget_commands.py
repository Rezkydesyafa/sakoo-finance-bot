"""Focused flow extracted from transaction message orchestration."""

from app.modules.budgets.service import (
    find_visible_expense_category_by_name,
    get_budget_for_category,
    get_budget_overview,
    upsert_category_budget,
)
from app.modules.transactions.transaction_flow import (
    BUDGET_CATEGORY_LIST_RE,
    BUDGET_HELP_RE,
    BUDGET_LIST_RE,
    BUDGET_REMAINING_RE,
    BUDGET_SET_RE,
    Category,
    Decimal,
    Session,
    TextTransactionResult,
    _active_pending_result,
    _category_name_from_alias,
    _synthetic_parse_result,
    extract_amount,
    format_rupiah,
    get_active_pending_state,
    re,
    select,
)


def _handle_budget_message(
    *,
    db: Session,
    user_id: int,
    text: str,
    source: str,
) -> TextTransactionResult | None:
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
