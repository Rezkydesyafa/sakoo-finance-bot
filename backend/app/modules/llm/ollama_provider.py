from __future__ import annotations

import httpx

from app.modules.llm.base import (
    BaseLlmProvider,
    LlmProviderConfig,
    LlmProviderError,
    build_finance_chat_messages,
    compact_error_detail,
    request_openai_chat_completion,
)


class OllamaProvider(BaseLlmProvider):
    """LLM provider that connects to a local Ollama instance.

    Ollama exposes an OpenAI-compatible API at ``/v1/chat/completions``,
    so we reuse the shared ``request_openai_chat_completion`` helper.
    No API key is required because the server runs locally on the VPS.
    """

    provider_name = "ollama"

    def __init__(self, config: LlmProviderConfig, *, base_url: str = "") -> None:
        super().__init__(config)
        self.base_url = (base_url or "http://localhost:11434").rstrip("/")

    @property
    def api_url(self) -> str:
        return f"{self.base_url}/v1/chat/completions"

    def answer_finance_question(self, message: str, *, context: str) -> str:
        if not self.config.model:
            raise LlmProviderError("ollama_model_missing")

        system_prompt, user_prompt = build_finance_chat_messages(
            message, context=context,
        )
        return request_openai_chat_completion(
            provider_name=self.provider_name,
            api_url=self.api_url,
            api_key="",
            model=self.config.model,
            prompt=user_prompt,
            system_prompt=system_prompt,
            timeout_seconds=self.config.timeout_seconds,
        )

    def is_available(self) -> bool:
        """Check whether the Ollama server is reachable."""
        try:
            response = httpx.get(
                f"{self.base_url}/api/tags",
                timeout=5.0,
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def has_model(self, model_name: str | None = None) -> bool:
        """Check whether a specific model is pulled on the Ollama server."""
        target = model_name or self.config.model
        if not target:
            return False

        try:
            response = httpx.get(
                f"{self.base_url}/api/tags",
                timeout=5.0,
            )
            response.raise_for_status()
            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            return any(target in m for m in models)
        except (httpx.HTTPError, ValueError, KeyError):
            return False
