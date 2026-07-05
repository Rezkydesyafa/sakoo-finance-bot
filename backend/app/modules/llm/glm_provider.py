from __future__ import annotations

from app.modules.llm.base import (
    BaseLlmProvider,
    LlmProviderError,
    build_finance_chat_prompt,
    request_openai_chat_completion,
)


class GlmProvider(BaseLlmProvider):
    provider_name = "glm"
    api_url = "https://open.bigmodel.cn/api/paas/v4/chat/completions"

    def answer_finance_question(self, message: str, *, context: str) -> str:
        if not self.config.model:
            raise LlmProviderError("glm_model_missing")

        return request_openai_chat_completion(
            provider_name=self.provider_name,
            api_url=self.api_url,
            api_key=self.config.api_key,
            model=self.config.model,
            prompt=build_finance_chat_prompt(message, context=context),
            timeout_seconds=self.config.timeout_seconds,
        )
