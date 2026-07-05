import pytest

from app.config import Settings
from app.modules.llm.base import LlmProviderError, build_finance_chat_prompt
from app.modules.llm.gemini_provider import GeminiProvider
from app.modules.llm.llm_router import answer_finance_question_with_llm, get_llm_providers


def test_llm_chat_prompt_stays_compact() -> None:
    prompt = build_finance_chat_prompt(
        "keuangan bulan ini aman nggak?",
        context="Saldo total: Rp100.000 Pengeluaran bulan ini: Rp50.000",
    )

    assert len(prompt) < 360
    assert "Sakoo finance bot" in prompt


def test_gemini_default_model_uses_flash_lite() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:")

    assert settings.llm_provider == "gemini,openrouter,ollama"
    assert settings.gemini_model == "gemini-3.1-flash-lite"
    assert GeminiProvider.model == "gemini-3.1-flash-lite"


def test_llm_provider_chain_reads_gemini_then_openrouter_then_ollama() -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        llm_provider="gemini,openrouter,ollama",
        gemini_api_key_1="gemini-key-one",
        gemini_api_key_2="gemini-key-two",
        openrouter_api_key="openrouter-key",
        gemini_model="gemini-test-model",
        openrouter_model="openrouter/test-model",
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
    )

    result = answer_finance_question_with_llm(
        "bulan ini aman?",
        context="Saldo total: Rp100.000 Pengeluaran bulan ini: Rp50.000",
        settings=settings,
    )

    assert result == "Aman, pengeluaran masih di bawah saldo."
