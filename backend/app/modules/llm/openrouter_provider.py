from __future__ import annotations

from typing import Any

import httpx

from app.modules.llm.base import (
    BaseLlmProvider,
    LlmProviderError,
    build_llm_prompt,
    parse_json_object,
    validate_llm_response,
)


class OpenRouterProvider(BaseLlmProvider):
    provider_name = "openrouter"
    model = "deepseek/deepseek-chat"
    api_url = "https://openrouter.ai/api/v1/chat/completions"

    def parse_transaction(self, message: str) -> dict[str, Any]:
        if not self.config.api_key:
            raise LlmProviderError("openrouter_api_key_missing")

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": build_llm_prompt(message)}],
            "temperature": 0,
            "max_tokens": 120,
        }
        try:
            response = httpx.post(
                self.api_url,
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                json=payload,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LlmProviderError("openrouter_request_failed") from exc

        return validate_llm_response(parse_json_object(_extract_chat_text(data)))


def _extract_chat_text(data: dict[str, Any]) -> str:
    try:
        return str(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmProviderError("openrouter_response_missing_text") from exc
