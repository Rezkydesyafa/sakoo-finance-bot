from __future__ import annotations

from app.modules.llm.base import (
    BaseLlmProvider,
    LlmProviderConfig,
    build_finance_chat_messages,
)


class CustomLlmProvider(BaseLlmProvider):
    def __init__(
        self,
        config: LlmProviderConfig,
        *,
        name: str,
        base_url: str,
    ) -> None:
        super().__init__(config)
        self.provider_name = f"custom:{name}"
        self.api_url = f"{base_url.rstrip('/')}/chat/completions"

    def answer_finance_question(self, message: str, *, context: str) -> str:
        system_prompt, user_prompt = build_finance_chat_messages(
            message,
            context=context,
        )
        return self.complete(
            user_prompt,
            system_prompt=system_prompt,
            temperature=0.4,
            max_tokens=500,
        )
