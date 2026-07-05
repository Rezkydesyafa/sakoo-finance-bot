from __future__ import annotations

from app.modules.llm.base import (
    BaseLlmProvider,
    LlmProviderError,
    build_finance_chat_messages,
    request_openai_chat_completion,
)


class OpenRouterProvider(BaseLlmProvider):
    provider_name = "openrouter"
    api_url = "https://openrouter.ai/api/v1/chat/completions"

    def answer_finance_question(self, message: str, *, context: str) -> str:
        if not self.config.model:
            raise LlmProviderError("openrouter_model_missing")

        system_prompt, user_prompt = build_finance_chat_messages(
            message, context=context,
        )
        return request_openai_chat_completion(
            provider_name=self.provider_name,
            api_url=self.api_url,
            api_key=self.config.api_key,
            model=self.config.model,
            prompt=user_prompt,
            system_prompt=system_prompt,
            timeout_seconds=self.config.timeout_seconds,
        )
