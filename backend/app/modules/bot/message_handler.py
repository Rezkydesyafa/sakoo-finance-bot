from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.modules.ai.ollama import ollama_available, parse_with_ollama
from app.modules.parser.service import ParsedMessage, parse_message

logger = logging.getLogger(__name__)

# If the rule-based parser confidence is below this threshold,
# try the AI parser as a fallback.
AI_FALLBACK_CONFIDENCE_THRESHOLD = 0.70


def parse_bot_text_message(
    *,
    db: Session,
    user_id: int,
    text: str,
    source: str,
    today: date | None = None,
) -> tuple[ParsedMessage, str | None]:
    """Parse a bot text message, with optional AI fallback.

    1. First, run the rule-based parser.
    2. If confidence is below threshold AND Ollama is available,
       try the AI parser as a fallback.
    3. Use the result with the higher confidence.
    """
    result = parse_message(text, source=source, today=today)

    # If rule-based confidence is good enough, return immediately.
    if result.confidence >= AI_FALLBACK_CONFIDENCE_THRESHOLD:
        return result, None

    # Try AI fallback.
    try:
        if ollama_available():
            ai_result = parse_with_ollama(text, source=source, today=today)
            if ai_result is not None and ai_result.confidence > result.confidence:
                logger.info(
                    "AI parser produced higher confidence (%.2f vs %.2f) for user %d",
                    ai_result.confidence,
                    result.confidence,
                    user_id,
                )
                return ai_result, None
    except Exception:
        logger.warning(
            "AI parser fallback failed for user %d, using rule-based result",
            user_id,
            exc_info=True,
        )

    return result, None
