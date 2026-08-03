"""Stable public facade for transaction message handling."""

from typing import Any

from app.modules.bot.message_handler import parse_bot_text_message as handle_bot_text_message
from app.modules.llm.llm_router import answer_finance_question_with_llm
from app.modules.transactions import transaction_flow as _flow

TextTransactionResult = _flow.TextTransactionResult
build_balance_response = _flow.build_balance_response
build_recent_transactions_response = _flow.build_recent_transactions_response
build_report_summary_response = _flow.build_report_summary_response
build_transaction_list_response = _flow.build_transaction_list_response
_build_llm_finance_context = _flow._build_llm_finance_context


def handle_text_transaction(*args: Any, **kwargs: Any) -> TextTransactionResult:
    _sync_overrides()
    return _flow.handle_text_transaction(*args, **kwargs)


def handle_telegram_text_transaction(*args: Any, **kwargs: Any) -> TextTransactionResult:
    _sync_overrides()
    return _flow.handle_telegram_text_transaction(*args, **kwargs)


def handle_whatsapp_text_transaction(*args: Any, **kwargs: Any) -> TextTransactionResult:
    _sync_overrides()
    return _flow.handle_whatsapp_text_transaction(*args, **kwargs)


def _sync_overrides() -> None:
    # Keep existing test/integration monkeypatch points compatible with the facade.
    _flow.answer_finance_question_with_llm = answer_finance_question_with_llm
    _flow.handle_bot_text_message = handle_bot_text_message


__all__ = [
    "TextTransactionResult",
    "answer_finance_question_with_llm",
    "build_balance_response",
    "build_recent_transactions_response",
    "build_report_summary_response",
    "build_transaction_list_response",
    "handle_telegram_text_transaction",
    "handle_bot_text_message",
    "handle_text_transaction",
    "handle_whatsapp_text_transaction",
]
