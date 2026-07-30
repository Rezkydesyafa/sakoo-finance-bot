from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.modules.ai.ollama import (
    TRANSACTION_PARSE_SYSTEM_PROMPT,
    build_transaction_parse_prompt,
    parse_transaction_response,
)
from app.modules.categories.service import list_categories
from app.modules.llm.llm_router import get_llm_providers
from app.modules.parser.schemas import INTENT_UNKNOWN
from app.modules.parser.service import ParsedMessage, parse_message

logger = logging.getLogger(__name__)


def parse_bot_text_message(
    *,
    db: Session,
    user_id: int,
    text: str,
    source: str,
    today: date | None = None,
) -> tuple[ParsedMessage, str | None]:
    """Interpret with configured LLM providers, then fall back to rules."""
    fallback_errors: list[str] = []
    try:
        providers = get_llm_providers()
        if providers:
            category_options = [
                (category.name, category.type)
                for category in list_categories(db, user_id)
            ]
            current_date = today or date.today()
            prompt = build_transaction_parse_prompt(
                text,
                today=current_date,
                category_options=category_options,
            )
            for provider in providers:
                try:
                    raw_result = provider.complete(
                        prompt,
                        system_prompt=TRANSACTION_PARSE_SYSTEM_PROMPT,
                        temperature=0.1,
                        max_tokens=320,
                    )
                    llm_result = parse_transaction_response(
                        raw_result,
                        source=source,
                        today=current_date,
                        category_options=category_options,
                        provider_name=provider.provider_name,
                    )
                except Exception as exc:
                    fallback_errors.append(
                        f"{provider.provider_name}:{type(exc).__name__}"
                    )
                    continue

                if llm_result is not None and llm_result.intent != INTENT_UNKNOWN:
                    logger.info(
                        "%s interpreted message for user %d",
                        provider.provider_name,
                        user_id,
                    )
                    return llm_result, None
                fallback_errors.append(f"{provider.provider_name}:invalid_result")
    except Exception:
        fallback_errors.append("llm_router_error")
        logger.warning(
            "LLM-first parser setup failed for user %d",
            user_id,
            exc_info=True,
        )

    fallback_error = ";".join(fallback_errors) or None
    if fallback_error:
        logger.warning(
            "LLM-first parsing failed for user %d; using rule parser (%s)",
            user_id,
            fallback_error,
        )
    return parse_message(text, source=source, today=today), fallback_error
