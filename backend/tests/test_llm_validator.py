from datetime import date
from decimal import Decimal

import pytest

from app.config import Settings
from app.modules.llm.base import (
    LlmProviderError,
    LlmResponseValidationError,
    expand_llm_response,
    parse_json_object,
    validate_llm_response,
)
from app.modules.llm.llm_router import get_llm_providers, parse_transaction_with_llm


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


@pytest.mark.parametrize(
    ("raw_confidence", "expected_confidence"),
    [
        (90, 0.9),
        ("90%", 0.9),
        ("0.91", 0.91),
    ],
)
def test_llm_validator_accepts_common_confidence_formats(
    raw_confidence: object,
    expected_confidence: float,
) -> None:
    payload = validate_llm_response(
        {
            "i": "ADD",
            "t": "expense",
            "a": 18000,
            "c": "MKN",
            "d": "ngopi di cafe",
            "dt": "today",
            "cf": raw_confidence,
            "ask": False,
        }
    )

    assert payload["cf"] == pytest.approx(expected_confidence)


@pytest.mark.parametrize(
    ("raw_ask", "expected_ask"),
    [
        ("false", False),
        ("true", True),
        (0, False),
        (1, True),
    ],
)
def test_llm_validator_accepts_common_ask_formats(
    raw_ask: object,
    expected_ask: bool,
) -> None:
    payload = validate_llm_response(
        {
            "i": "ADD",
            "t": "expense",
            "a": 18000,
            "c": "MKN",
            "d": "ngopi di cafe",
            "dt": "today",
            "cf": 0.91,
            "ask": raw_ask,
        }
    )

    assert payload["ask"] is expected_ask


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


def test_llm_provider_chain_reads_multiple_gemini_keys_before_openrouter() -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        llm_provider="gemini,openrouter",
        gemini_api_key_1="gemini-key-one",
        gemini_api_key_2="gemini-key-two",
        openrouter_api_key="openrouter-key",
        gemini_model="gemini-test-model",
        openrouter_model="openrouter/test-model",
    )

    providers = get_llm_providers(settings)

    assert [provider.provider_name for provider in providers] == [
        "gemini",
        "gemini",
        "openrouter",
    ]
    assert [provider.config.api_key for provider in providers] == [
        "gemini-key-one",
        "gemini-key-two",
        "openrouter-key",
    ]
    assert [provider.config.model for provider in providers] == [
        "gemini-test-model",
        "gemini-test-model",
        "openrouter/test-model",
    ]


def test_llm_provider_chain_falls_back_to_next_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingProvider:
        provider_name = "gemini"

        def parse_transaction(self, _message: str) -> dict[str, object]:
            raise LlmProviderError("gemini_request_failed")

    class SuccessProvider:
        provider_name = "openrouter"

        def parse_transaction(self, _message: str) -> dict[str, object]:
            return {
                "i": "ADD",
                "t": "expense",
                "a": 18000,
                "c": "MKN",
                "d": "ngopi di cafe",
                "dt": "today",
                "cf": 0.91,
                "ask": False,
            }

    monkeypatch.setattr(
        "app.modules.llm.llm_router.get_llm_providers",
        lambda _settings: [FailingProvider(), SuccessProvider()],
    )
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        llm_provider="gemini,openrouter",
    )

    result = parse_transaction_with_llm(
        "abis ngopi di cafe 18k",
        source="manual_test",
        today=date(2026, 6, 29),
        settings=settings,
    )

    assert result["amount"] == Decimal("18000")
    assert result["category"] == "Makanan"
    assert result["metadata"]["llm_provider"] == "openrouter"
