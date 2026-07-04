from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx


FINANCE_CHAT_PROMPT_TEMPLATE = (
    "Role:Sakoo finance bot. Reply ID, max 4 short lines. "
    "Use ctx numbers only; do not invent. "
    "If outside finance/Sakoo, say you only help finance/Sakoo. "
    'Ctx:{context} Q:"{message}"'
)


class LlmProviderError(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True)
class LlmProviderConfig:
    api_key: str
    timeout_seconds: float
    model: str | None = None


class BaseLlmProvider:
    provider_name: str

    def __init__(self, config: LlmProviderConfig) -> None:
        self.config = config

    def answer_finance_question(self, message: str, *, context: str) -> str:
        raise LlmProviderError(f"{self.provider_name}_finance_chat_not_supported")


def build_finance_chat_prompt(message: str, *, context: str) -> str:
    compact_message = re.sub(r"\s+", " ", message.strip())
    escaped_message = compact_message[:300].replace("\\", "\\\\").replace('"', '\\"')
    compact_context = re.sub(r"\s+", " ", context.strip())[:900]
    return FINANCE_CHAT_PROMPT_TEMPLATE.replace("{message}", escaped_message).replace(
        "{context}",
        compact_context,
    )


def compact_error_detail(raw_text: str, *, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(raw_text or "")).strip()
    if not text:
        return "empty_response"
    return text[:limit]


def request_openai_chat_completion(
    *,
    provider_name: str,
    api_url: str,
    api_key: str,
    model: str,
    prompt: str,
    timeout_seconds: float,
    temperature: float = 0.4,
    max_tokens: int = 160,
) -> str:
    if not api_key:
        raise LlmProviderError(f"{provider_name}_api_key_missing")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        response = httpx.post(
            api_url,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        detail = compact_error_detail(exc.response.text)
        raise LlmProviderError(
            f"{provider_name}_request_failed:{exc.response.status_code}:{detail}"
        ) from None
    except httpx.HTTPError as exc:
        raise LlmProviderError(f"{provider_name}_request_failed:{type(exc).__name__}") from None
    except ValueError as exc:
        raise LlmProviderError(f"{provider_name}_response_invalid_json") from exc

    return _extract_openai_chat_text(data, provider_name).strip()


def _extract_openai_chat_text(data: dict[str, Any], provider_name: str) -> str:
    try:
        return str(data["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmProviderError(f"{provider_name}_response_missing_text") from exc
