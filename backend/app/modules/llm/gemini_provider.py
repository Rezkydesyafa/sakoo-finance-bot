from __future__ import annotations

from typing import Any

import httpx

from app.modules.llm.base import (
    BaseLlmProvider,
    LlmProviderError,
    build_finance_chat_prompt,
    compact_error_detail,
)


class GeminiProvider(BaseLlmProvider):
    provider_name = "gemini"
    model = "gemini-1.5-flash"

    def answer_finance_question(self, message: str, *, context: str) -> str:
        if not self.config.api_key:
            raise LlmProviderError("gemini_api_key_missing")

        model = self.config.model or self.model
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model}:generateContent"
        )
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": build_finance_chat_prompt(message, context=context)}
                    ]
                }
            ],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 160},
        }
        try:
            response = httpx.post(
                url,
                params={"key": self.config.api_key},
                json=payload,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            detail = compact_error_detail(exc.response.text)
            raise LlmProviderError(
                f"gemini_request_failed:{exc.response.status_code}:{detail}"
            ) from None
        except httpx.HTTPError as exc:
            raise LlmProviderError(
                f"gemini_request_failed:{type(exc).__name__}"
            ) from None
        except ValueError as exc:
            raise LlmProviderError("gemini_response_invalid_json") from exc

        try:
            return str(data["candidates"][0]["content"]["parts"][0]["text"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmProviderError("gemini_response_missing_text") from exc
