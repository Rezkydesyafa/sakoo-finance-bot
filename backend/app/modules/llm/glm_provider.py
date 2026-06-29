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


class GlmProvider(BaseLlmProvider):
    provider_name = "glm"
    model = "glm-4-flash"
    api_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    def parse_transaction(self, message: str) -> dict[str, Any]:
        if not self.config.api_key:
            raise LlmProviderError("glm_api_key_missing")

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
            raise LlmProviderError("glm_request_failed") from exc

        return validate_llm_response(parse_json_object(_extract_chat_text(data, "glm")))


def _extract_chat_text(data: dict[str, Any], provider: str) -> str:
    try:
        return str(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmProviderError(f"{provider}_response_missing_text") from exc
