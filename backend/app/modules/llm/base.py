from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx


# ── System prompt (persona, rules, capabilities) ──────────────────────
FINANCE_CHAT_SYSTEM_PROMPT = (
    "Kamu adalah Sakoo 🐱, asisten keuangan pribadi yang ramah dan seru via chat. "
    "Kamu berbicara santai seperti teman, pakai emoji secara alami, dan selalu menyapa hangat.\n\n"
    "FITUR UTAMA: catat transaksi, cek saldo, set/cek budget, laporan keuangan, "
    "export PDF, OCR struk, voice note.\n\n"
    "ATURAN RESPONS:\n"
    "- Jawab dalam Bahasa Indonesia yang santai dan natural\n"
    "- Gunakan emoji yang relevan (💰📊✨🎯💡🤔👋 dll) tapi jangan berlebihan\n"
    "- Panggil nama user jika tersedia di konteks\n"
    "- Maksimal 8 baris pendek, jelas dan mudah dipahami\n"
    "- Gunakan angka dari konteks saja, JANGAN mengarang angka\n"
    "- Mulai respons dengan sapaan hangat jika sesuai (Halo!, Hai!, Oke!, Siap!)\n\n"
    "BOLEH DIJAWAB:\n"
    "- Sapaan dan perkenalan\n"
    "- Pertanyaan tentang fitur bot Sakoo\n"
    "- Pertanyaan keuangan berdasarkan data user (saldo, pengeluaran, dll)\n"
    "- Pertanyaan EDUKASI keuangan umum (tips menabung, budgeting, cara mengatur uang, "
    "pentingnya financial planning, investasi dasar, dll)\n"
    "- Tips dan saran keuangan berdasarkan data pengeluaran user\n\n"
    "JANGAN DIJAWAB:\n"
    "- Topik di luar keuangan → arahkan kembali dengan sopan dan emoji 😊"
)

# ── User prompt template (context + question) ─────────────────────────
FINANCE_CHAT_USER_TEMPLATE = 'Konteks:\n{context}\n\nPertanyaan: "{message}"'


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

    def complete(
        self,
        prompt: str,
        *,
        system_prompt: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 500,
    ) -> str:
        if not self.config.model:
            raise LlmProviderError(f"{self.provider_name}_model_missing")

        api_url = getattr(self, "api_url", None)
        if not api_url:
            raise LlmProviderError(f"{self.provider_name}_completion_not_supported")

        return request_openai_chat_completion(
            provider_name=self.provider_name,
            api_url=api_url,
            api_key=self.config.api_key,
            model=self.config.model,
            prompt=prompt,
            system_prompt=system_prompt,
            timeout_seconds=self.config.timeout_seconds,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def answer_finance_question(self, message: str, *, context: str) -> str:
        raise LlmProviderError(f"{self.provider_name}_finance_chat_not_supported")


def build_finance_chat_messages(
    message: str,
    *,
    context: str,
) -> tuple[str, str]:
    """Return ``(system_prompt, user_prompt)`` for multi-message LLM calls."""
    compact_message = re.sub(r"\s+", " ", message.strip())[:300]
    compact_context = re.sub(r"\s+", " ", context.strip())[:1600]
    user_prompt = FINANCE_CHAT_USER_TEMPLATE.replace(
        "{message}", compact_message,
    ).replace("{context}", compact_context)
    return FINANCE_CHAT_SYSTEM_PROMPT, user_prompt


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
    max_tokens: int = 500,
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
