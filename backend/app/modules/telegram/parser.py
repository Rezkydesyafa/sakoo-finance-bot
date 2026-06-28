from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ParsedTelegramMessage:
    update_id: int
    message_id: int | None
    chat_id: str | None
    platform_user_id: str | None
    username: str | None
    first_name: str | None
    last_name: str | None
    text: str | None
    message_type: str

    def to_log_payload(self) -> dict[str, Any]:
        return asdict(self)


def parse_telegram_update(update: dict[str, Any]) -> ParsedTelegramMessage:
    update_id = update.get("update_id")
    if not isinstance(update_id, int):
        raise ValueError("missing_update_id")

    message = update.get("message") or update.get("edited_message")
    if not isinstance(message, dict):
        return ParsedTelegramMessage(
            update_id=update_id,
            message_id=None,
            chat_id=None,
            platform_user_id=None,
            username=None,
            first_name=None,
            last_name=None,
            text=None,
            message_type="unsupported",
        )

    chat = message.get("chat")
    sender = message.get("from")
    chat_id = _as_str(chat.get("id")) if isinstance(chat, dict) else None
    platform_user_id = _as_str(sender.get("id")) if isinstance(sender, dict) else None
    text = message.get("text")

    return ParsedTelegramMessage(
        update_id=update_id,
        message_id=message.get("message_id") if isinstance(message.get("message_id"), int) else None,
        chat_id=chat_id,
        platform_user_id=platform_user_id,
        username=sender.get("username") if isinstance(sender, dict) else None,
        first_name=sender.get("first_name") if isinstance(sender, dict) else None,
        last_name=sender.get("last_name") if isinstance(sender, dict) else None,
        text=text if isinstance(text, str) else None,
        message_type="text" if isinstance(text, str) else "unsupported",
    )


def telegram_identifier_candidates(parsed: ParsedTelegramMessage) -> list[str]:
    return [
        value
        for value in [parsed.platform_user_id, parsed.chat_id]
        if value
    ]


def _as_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
