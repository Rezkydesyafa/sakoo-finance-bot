import json

import httpx
import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

from app.config import Settings
from app.modules.llm.base import LlmProviderError, build_finance_chat_messages
from app.modules.llm.custom_provider import CustomLlmProvider
from app.modules.llm.llm_router import answer_finance_question_with_llm, get_llm_providers


def test_llm_chat_prompt_stays_compact() -> None:
    system_prompt, user_prompt = build_finance_chat_messages(
        "keuangan bulan ini aman nggak?",
        context="Saldo total: Rp100.000 Pengeluaran bulan ini: Rp50.000",
    )

    assert len(system_prompt) + len(user_prompt) < 2200
    assert "Sakoo" in system_prompt
    assert "Rp100.000" in user_prompt


def test_gemini_model_is_read_from_settings() -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        llm_provider="gemini,openrouter,ollama",
        gemini_model="gemini-3.1-flash-lite",
        glm_model="glm-4-flash",
        openrouter_model="deepseek/deepseek-chat",
        deepseek_model="deepseek-chat",
        ollama_model="qwen2.5:1.5b",
    )

    assert settings.llm_provider == "gemini,openrouter,ollama"
    assert settings.gemini_model == "gemini-3.1-flash-lite"


def test_llm_provider_chain_reads_gemini_then_openrouter_then_ollama() -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        llm_provider="gemini,openrouter,ollama",
        gemini_api_key_1="gemini-key-one",
        gemini_api_key_2="gemini-key-two",
        openrouter_api_key="openrouter-key",
        gemini_model="gemini-test-model",
        glm_model="glm-test-model",
        openrouter_model="openrouter/test-model",
        deepseek_model="deepseek-test-model",
        ollama_model="ollama/test-model",
    )

    providers = get_llm_providers(settings)

    assert [provider.provider_name for provider in providers] == [
        "gemini",
        "gemini",
        "openrouter",
        "ollama",
    ]
    assert [provider.config.api_key for provider in providers] == [
        "gemini-key-one",
        "gemini-key-two",
        "openrouter-key",
        "",
    ]
    assert [provider.config.model for provider in providers] == [
        "gemini-test-model",
        "gemini-test-model",
        "openrouter/test-model",
        "ollama/test-model",
    ]


def test_llm_provider_chain_infers_enabled_providers_from_api_keys() -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        llm_provider="none",
        gemini_model="gemini-3.1-flash-lite",
        glm_model="glm-test-model",
        openrouter_model="openrouter/test-model",
        deepseek_model="deepseek-test-model",
        ollama_model="ollama/test-model",
        gemini_api_key="gemini-key",
        gemini_api_key_1="",
        gemini_api_key_2="",
        gemini_api_keys="",
        openrouter_api_key="openrouter-key",
    )

    providers = get_llm_providers(settings)

    assert [provider.provider_name for provider in providers] == ["gemini", "openrouter"]


def test_llm_chat_falls_back_to_next_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingProvider:
        provider_name = "gemini"

        def answer_finance_question(self, _message: str, *, context: str) -> str:
            raise LlmProviderError("gemini_request_failed")

    class SuccessProvider:
        provider_name = "openrouter"

        def answer_finance_question(self, _message: str, *, context: str) -> str:
            assert "Saldo total" in context
            return "Aman, pengeluaran masih di bawah saldo."

    monkeypatch.setattr(
        "app.modules.llm.llm_router.get_llm_providers",
        lambda _settings: [FailingProvider(), SuccessProvider()],
    )
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        llm_provider="gemini,openrouter",
        gemini_model="gemini-3.1-flash-lite",
        glm_model="glm-test-model",
        openrouter_model="openrouter/test-model",
        deepseek_model="deepseek-test-model",
        ollama_model="ollama/test-model",
    )

    result = answer_finance_question_with_llm(
        "bulan ini aman?",
        context="Saldo total: Rp100.000 Pengeluaran bulan ini: Rp50.000",
        settings=settings,
    )

    assert result == "Aman, pengeluaran masih di bawah saldo."


@pytest.mark.parametrize(
    "custom_providers",
    [
        {
            "9router": {
                "base_url": "http://127.0.0.1:20128/v1",
                "api_key": "nine-router-key",
                "model": "premium-coding",
            }
        },
        {
            "9router": {
                "base_url": "http://127.0.0.1:20128/v1",
                "api_key": "nine-router-key",
                "model": "premium-coding",
            },
            "backup": {
                "base_url": "https://provider.example/v1",
                "api_key": "backup-key",
                "model": "backup-model",
            },
        },
    ],
)
def test_settings_parse_named_custom_providers_from_json(
    monkeypatch: pytest.MonkeyPatch,
    custom_providers: dict[str, dict[str, str]],
) -> None:
    monkeypatch.setenv("CUSTOM_LLM_PROVIDERS", json.dumps(custom_providers))
    settings = _settings(
        llm_provider="custom:9router",
        _env_file=None,
    )

    assert set(settings.custom_llm_providers) == set(custom_providers)
    assert settings.custom_llm_providers["9router"].model == "premium-coding"


@pytest.mark.parametrize(
    ("llm_provider", "custom_providers"),
    [
        ("custom", {}),
        ("custom:missing", {}),
        (
            "custom:9router",
            {
                "9Router": {
                    "base_url": "http://127.0.0.1:20128/v1",
                    "api_key": "key",
                    "model": "model",
                }
            },
        ),
        (
            "custom:9router",
            {
                "9router": {
                    "base_url": "not-a-url",
                    "api_key": "key",
                    "model": "model",
                }
            },
        ),
        (
            "custom:9router",
            {
                "9router": {
                    "base_url": "http://127.0.0.1:20128/v1/chat/completions",
                    "api_key": "key",
                    "model": "model",
                }
            },
        ),
        (
            "custom:9router",
            {
                "9router": {
                    "base_url": "http://127.0.0.1:20128/v1",
                    "api_key": " ",
                    "model": "model",
                }
            },
        ),
        (
            "custom:9router",
            {
                "9router": {
                    "base_url": "http://127.0.0.1:20128/v1",
                    "api_key": "key",
                    "model": "",
                }
            },
        ),
    ],
)
def test_custom_provider_configuration_fails_fast(
    llm_provider: str,
    custom_providers: dict[str, dict[str, str]],
) -> None:
    with pytest.raises(ValidationError):
        _settings(
            llm_provider=llm_provider,
            custom_llm_providers=custom_providers,
            _env_file=None,
        )


def test_malformed_custom_provider_json_fails_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CUSTOM_LLM_PROVIDERS", "{not-json")

    with pytest.raises(SettingsError):
        _settings(llm_provider="none", _env_file=None)


def test_custom_providers_can_be_interleaved_in_fallback_chain() -> None:
    settings = _settings(
        llm_provider="custom:9router,gemini,custom:backup,ollama",
        gemini_api_key="gemini-key",
        custom_llm_providers={
            "9router": {
                "base_url": "http://host.docker.internal:20128/v1",
                "api_key": "nine-router-key",
                "model": "premium-coding",
            },
            "backup": {
                "base_url": "https://provider.example/v1",
                "api_key": "backup-key",
                "model": "backup-model",
            },
        },
    )

    providers = get_llm_providers(settings)

    assert [provider.provider_name for provider in providers] == [
        "custom:9router",
        "gemini",
        "custom:backup",
        "ollama",
    ]
    assert isinstance(providers[0], CustomLlmProvider)
    assert providers[0].api_url == (
        "http://host.docker.internal:20128/v1/chat/completions"
    )
    assert providers[2].api_url == "https://provider.example/v1/chat/completions"


def test_custom_provider_sends_openai_compatible_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = get_llm_providers(
        _settings(
            llm_provider="custom:9router",
            custom_llm_providers={
                "9router": {
                    "base_url": "http://127.0.0.1:20128/v1/",
                    "api_key": "nine-router-key",
                    "model": "premium-coding",
                }
            },
        )
    )[0]
    captured: dict[str, object] = {}

    def fake_post(
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, object],
        timeout: float,
    ) -> httpx.Response:
        captured.update(
            url=url,
            headers=headers,
            payload=json,
            timeout=timeout,
        )
        content = (
            '{"intent":"get_balance"}'
            if json["temperature"] == 0.1
            else "Keuangan masih aman."
        )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": content}}]},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx, "post", fake_post)

    answer = provider.answer_finance_question(
        "bulan ini aman?",
        context="Saldo total: Rp100.000",
    )

    assert answer == "Keuangan masih aman."
    assert captured["url"] == "http://127.0.0.1:20128/v1/chat/completions"
    assert captured["headers"] == {"Authorization": "Bearer nine-router-key"}
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "premium-coding"
    assert payload["stream"] is False
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["role"] == "user"

    transaction_result = provider.complete(
        "parse transaction",
        system_prompt="return JSON",
        temperature=0.1,
        max_tokens=320,
    )

    assert transaction_result == '{"intent":"get_balance"}'
    transaction_payload = captured["payload"]
    assert isinstance(transaction_payload, dict)
    assert transaction_payload["temperature"] == 0.1
    assert transaction_payload["max_tokens"] == 320


def test_finance_chat_falls_back_after_custom_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FailingCustomProvider:
        provider_name = "custom:9router"

        def answer_finance_question(self, _message: str, *, context: str) -> str:
            raise LlmProviderError("custom:9router_request_failed")

    class SuccessProvider:
        provider_name = "gemini"

        def answer_finance_question(self, _message: str, *, context: str) -> str:
            return "Fallback berhasil."

    monkeypatch.setattr(
        "app.modules.llm.llm_router.get_llm_providers",
        lambda _settings: [FailingCustomProvider(), SuccessProvider()],
    )

    result = answer_finance_question_with_llm(
        "bulan ini aman?",
        context="Saldo total: Rp100.000",
        settings=_settings(llm_provider="gemini"),
    )

    assert result == "Fallback berhasil."


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "database_url": "sqlite+pysqlite:///:memory:",
        "llm_provider": "none",
        "gemini_api_key": "",
        "gemini_api_key_1": "",
        "gemini_api_key_2": "",
        "gemini_api_keys": "",
        "gemini_model": "gemini-test-model",
        "glm_model": "glm-test-model",
        "openrouter_model": "openrouter/test-model",
        "deepseek_model": "deepseek-test-model",
        "ollama_model": "ollama/test-model",
    }
    values.update(overrides)
    return Settings(**values)
