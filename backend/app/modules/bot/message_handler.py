from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.modules.parser.service import ParsedMessage, parse_message


def parse_bot_text_message(
    *,
    db: Session,
    user_id: int,
    text: str,
    source: str,
    today: date | None = None,
) -> tuple[ParsedMessage, str | None]:
    return parse_message(text, source=source, today=today), None
