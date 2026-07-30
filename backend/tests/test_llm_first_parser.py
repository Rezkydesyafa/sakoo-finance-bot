from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.modules.bot import message_handler
from app.modules.parser.service import ParsedMessage


class FakeProvider:
    provider_name = "fake"

    def __init__(self, response: str | Exception) -> None:
        self.response = response

    def complete(self, *_args, **_kwargs) -> str:
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_llm_result_is_used_before_rule_parser(monkeypatch) -> None:
    provider = FakeProvider(
        """
        {
          "intent": "add_transaction",
          "type": "expense",
          "amount": 25000,
          "category": "Kopi Kampus",
          "description": "ngopi di kampus",
          "transaction_date": "2026-07-24",
          "period": null,
          "limit": null,
          "sort_order": null,
          "category_filter": null
        }
        """
    )
    monkeypatch.setattr(message_handler, "get_llm_providers", lambda: [provider])
    monkeypatch.setattr(
        message_handler,
        "list_categories",
        lambda _db, _user_id: [
            SimpleNamespace(name="Kopi Kampus", type="both"),
        ],
    )
    monkeypatch.setattr(
        message_handler,
        "parse_message",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("rule parser must not run")
        ),
    )

    result, fallback_error = message_handler.parse_bot_text_message(
        db=object(),
        user_id=7,
        text="tadi nongkrong sambil ngopi habis 25 ribu",
        source="telegram_text",
        today=date(2026, 7, 24),
    )

    assert result.amount == Decimal("25000")
    assert result.category == "Kopi Kampus"
    assert result.category_source == "llm_fake"
    assert fallback_error is None


def test_rule_parser_is_used_when_llm_fails(monkeypatch) -> None:
    fallback = ParsedMessage(
        intent="get_balance",
        type=None,
        amount=None,
        category=None,
        description="saldo",
        transaction_date=date(2026, 7, 24),
        source="whatsapp_text",
        confidence=1.0,
        need_confirmation=False,
        reasons=[],
    )
    monkeypatch.setattr(
        message_handler,
        "get_llm_providers",
        lambda: [FakeProvider(RuntimeError("offline"))],
    )
    monkeypatch.setattr(message_handler, "list_categories", lambda *_args: [])
    monkeypatch.setattr(message_handler, "parse_message", lambda *_args, **_kwargs: fallback)

    result, fallback_error = message_handler.parse_bot_text_message(
        db=object(),
        user_id=7,
        text="saldo gue berapa?",
        source="whatsapp_text",
        today=date(2026, 7, 24),
    )

    assert result is fallback
    assert fallback_error == "fake:RuntimeError"
