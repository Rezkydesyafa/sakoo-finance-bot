"""Focused flow extracted from transaction message orchestration."""

from app.modules.bot.response_templates import (
    format_llm_error_response,
    format_rate_limit_response,
)
from app.modules.budgets.service import get_budget_overview
from app.modules.llm.base import LlmProviderError
from app.modules.llm.llm_router import LlmRateLimitExceeded
from app.modules.transactions.transaction_flow import (
    INTENT_UNKNOWN,
    ParsedMessage,
    Session,
    TextTransactionResult,
    _synthetic_parse_result,
    _user_first_name,
    answer_finance_question_with_llm,
    date,
    format_rupiah,
    list_transactions,
    sum_transactions,
    timedelta,
    top_expense_category,
)


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


def _build_llm_finance_context(db: Session, user_id: int) -> str:
    today = date.today()
    name = _user_first_name(db, user_id)
    budget = get_budget_overview(db, user_id, today=today)
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
    budget_text = (
        f"total {format_rupiah(budget.total_budgeted)}, "
        f"terpakai {format_rupiah(budget.total_spent)}, "
        f"sisa {format_rupiah(budget.total_remaining)}"
        if budget.items
        else "belum diset"
    )
    budget_items = "; ".join(
        f"{item.category_name}: limit {format_rupiah(item.monthly_limit)}, "
        f"terpakai {format_rupiah(item.spent)}, sisa {format_rupiah(item.remaining)}, "
        f"status {item.status}"
        for item in budget.items
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
            f"Budget bulan ini: {budget_text}",
            "Rincian budget: " + (budget_items or "belum ada"),
            "Transaksi terbaru: " + ("; ".join(recent_lines) if recent_lines else "belum ada"),
        ]
    )
