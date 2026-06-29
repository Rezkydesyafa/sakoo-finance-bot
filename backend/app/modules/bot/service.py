from sqlalchemy.orm import Session

from app.modules.bot.message_handler import parse_bot_text_message
from app.modules.parser.service import ParsedMessage


def handle_bot_text_message(
    *,
    db: Session,
    user_id: int,
    text: str,
    source: str,
) -> tuple[ParsedMessage, str | None]:
    """Application entry point for natural-language bot text parsing."""
    return parse_bot_text_message(db=db, user_id=user_id, text=text, source=source)

