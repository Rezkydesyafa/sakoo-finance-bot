from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx


# ── System prompt (persona, rules, capabilities) ──────────────────────
FINANCE_CHAT_SYSTEM_PROMPT = (
    "Kamu adalah Sakoo, asisten keuangan pribadi via chat. "
    "Fitur: catat transaksi, cek saldo, laporan keuangan, export PDF, OCR struk, voice note. "
    "Jawab ramah, terasa personal, dalam Bahasa Indonesia, maksimal 4 baris pendek. "
    "Panggil nama user jika tersedia di konteks. "
    "Gunakan angka dari konteks saja, jangan mengarang angka. "
    "Boleh jawab: sapaan, tanya fitur bot, dan pertanyaan keuangan. "
    "Jika topik di luar keuangan, arahkan kembali ke keuangan dengan sopan."
)

# ── User prompt template (context + question) ─────────────────────────
FINANCE_CHAT_USER_TEMPLATE = 'Konteks:\n{context}\n\nPertanyaan: "{message}"'

# Legacy single-string template kept for backward compatibility with
# ``build_finance_chat_prompt``.
FINANCE_CHAT_PROMPT_TEMPLATE = (
    "Role:Sakoo, asisten keuangan chat. Reply ID, max 4 short lines. "
    "Use ctx numbers only; do not invent. "
    "Answer greetings, bot features, and finance questions. "
    "If off-topic, politely redirect to finance. "
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


def build_finance_chat_messages(
    message: str,
    *,
    context: str,
) -> tuple[str, str]:
    """Return ``(system_prompt, user_prompt)`` for multi-message LLM calls."""
    compact_message = re.sub(r"\s+", " ", message.strip())[:300]
    compact_context = re.sub(r"\s+", " ", context.strip())[:900]
    user_prompt = FINANCE_CHAT_USER_TEMPLATE.replace(
        "{message}", compact_message,
    ).replace("{context}", compact_context)
    return FINANCE_CHAT_SYSTEM_PROMPT, user_prompt


def build_finance_chat_prompt(message: str, *, context: str) -> str:
    """Legacy single-string prompt for backward compatibility."""
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
    max_tokens: int = 300,
    system_prompt: str | None = None,
) -> str:
    if not api_key and provider_name != "ollama":
        raise LlmProviderError(f"{provider_name}_api_key_missing")

    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    messages: list[dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        response = httpx.post(
            api_url,
            headers=headers,
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
