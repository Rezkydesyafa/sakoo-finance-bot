from datetime import date
from decimal import Decimal

import pytest

from app.modules.llm.base import (
    LlmResponseValidationError,
    expand_llm_response,
    parse_json_object,
    validate_llm_response,
)


def test_llm_validator_accepts_compact_prompt_shape() -> None:
    payload = validate_llm_response(
        {
            "i": "ADD",
            "t": "income",
            "a": 100000,
            "c": "USK",
            "d": "uang saku",
            "dt": "today",
            "cf": 0.92,
            "ask": False,
        }
    )

    assert payload["i"] == "ADD"
    assert payload["a"] == 100000
    assert payload["ask"] is False


def test_llm_validator_rejects_invalid_json_shape() -> None:
    with pytest.raises(LlmResponseValidationError):
        validate_llm_response({"i": "ADD"})

    with pytest.raises(LlmResponseValidationError):
        validate_llm_response(
            {
                "i": "BAD",
                "t": "income",
                "a": 100000,
                "c": "USK",
                "d": "uang saku",
                "dt": "today",
                "cf": 0.92,
                "ask": False,
            }
        )


def test_llm_expander_maps_compact_codes_to_backend_shape() -> None:
    result = expand_llm_response(
        {
            "i": "ADD",
            "t": "income",
            "a": 100000,
            "c": "USK",
            "d": "uang saku",
            "dt": "today",
            "cf": 0.92,
            "ask": False,
        },
        source="telegram_text",
        today=date(2026, 6, 29),
    )

    assert result["intent"] == "add_transaction"
    assert result["type"] == "income"
    assert result["amount"] == Decimal("100000")
    assert result["category"] == "Uang Saku"
    assert result["transaction_date"] == date(2026, 6, 29)
    assert result["need_confirmation"] is False


def test_parse_json_object_extracts_json_without_raw_response_storage() -> None:
    payload = parse_json_object('{"i":"HELP","t":"none","a":0,"c":"LNY","d":"","dt":"unknown","cf":1,"ask":false}')
    assert payload["i"] == "HELP"
