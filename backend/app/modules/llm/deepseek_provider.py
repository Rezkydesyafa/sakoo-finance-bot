from __future__ import annotations

from app.modules.llm.base import (
    BaseLlmProvider,
    build_finance_chat_prompt,
    request_openai_chat_completion,
)


class DeepSeekProvider(BaseLlmProvider):
    provider_name = "deepseek"
    model = "deepseek-chat"
    api_url = "https://api.deepseek.com/chat/completions"

    def answer_finance_question(self, message: str, *, context: str) -> str:
        return request_openai_chat_completion(
            provider_name=self.provider_name,
            api_url=self.api_url,
            api_key=self.config.api_key,
            model=self.config.model or self.model,
            prompt=build_finance_chat_prompt(message, context=context),
            timeout_seconds=self.config.timeout_seconds,
        )
