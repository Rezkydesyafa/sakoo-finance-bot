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
    file_id: str | None = None
    file_unique_id: str | None = None
    mime_type: str | None = None
    file_name: str | None = None
    duration_seconds: float | None = None
    callback_query_id: str | None = None
    callback_data: str | None = None

    def to_log_payload(self) -> dict[str, Any]:
        return asdict(self)


def parse_telegram_update(update: dict[str, Any]) -> ParsedTelegramMessage:
    update_id = update.get("update_id")
    if not isinstance(update_id, int):
        raise ValueError("missing_update_id")

    callback_query = update.get("callback_query")
    if isinstance(callback_query, dict):
        return _parse_callback_query(update_id, callback_query)

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
            file_id=None,
            file_unique_id=None,
            mime_type=None,
            file_name=None,
            duration_seconds=None,
            callback_query_id=None,
            callback_data=None,
        )

    chat = message.get("chat")
    sender = message.get("from")
    chat_id = _as_str(chat.get("id")) if isinstance(chat, dict) else None
    platform_user_id = _as_str(sender.get("id")) if isinstance(sender, dict) else None
    text = message.get("text")
    voice = message.get("voice")
    audio = message.get("audio")
    media = voice if isinstance(voice, dict) else audio if isinstance(audio, dict) else None

    return ParsedTelegramMessage(
        update_id=update_id,
        message_id=(
            message.get("message_id")
            if isinstance(message.get("message_id"), int)
            else None
        ),
        chat_id=chat_id,
        platform_user_id=platform_user_id,
        username=sender.get("username") if isinstance(sender, dict) else None,
        first_name=sender.get("first_name") if isinstance(sender, dict) else None,
        last_name=sender.get("last_name") if isinstance(sender, dict) else None,
        text=text if isinstance(text, str) else None,
        message_type=_detect_message_type(text=text, voice=voice, audio=audio),
        file_id=_as_str(media.get("file_id")) if isinstance(media, dict) else None,
        file_unique_id=_as_str(media.get("file_unique_id")) if isinstance(media, dict) else None,
        mime_type=_as_optional_str(media.get("mime_type")) if isinstance(media, dict) else None,
        file_name=_as_optional_str(media.get("file_name")) if isinstance(media, dict) else None,
        duration_seconds=(
            _positive_float(media.get("duration")) if isinstance(media, dict) else None
        ),
        callback_query_id=None,
        callback_data=None,
    )


def telegram_identifier_candidates(parsed: ParsedTelegramMessage) -> list[str]:
    return [
        value
        for value in [parsed.platform_user_id, parsed.chat_id]
        if value
    ]


def _parse_callback_query(
    update_id: int,
    callback_query: dict[str, Any],
) -> ParsedTelegramMessage:
    sender = callback_query.get("from")
    message = callback_query.get("message")
    chat = message.get("chat") if isinstance(message, dict) else None
    data = callback_query.get("data")

    return ParsedTelegramMessage(
        update_id=update_id,
        message_id=(
            message.get("message_id")
            if isinstance(message, dict) and isinstance(message.get("message_id"), int)
            else None
        ),
        chat_id=_as_str(chat.get("id")) if isinstance(chat, dict) else None,
        platform_user_id=_as_str(sender.get("id")) if isinstance(sender, dict) else None,
        username=sender.get("username") if isinstance(sender, dict) else None,
        first_name=sender.get("first_name") if isinstance(sender, dict) else None,
        last_name=sender.get("last_name") if isinstance(sender, dict) else None,
        text=None,
        message_type="callback_query",
        callback_query_id=_as_str(callback_query.get("id")),
        callback_data=data if isinstance(data, str) else None,
    )


def _as_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_optional_str(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _detect_message_type(
    *,
    text: object,
    voice: object,
    audio: object,
) -> str:
    if isinstance(text, str):
        return "text"
    if isinstance(voice, dict) or isinstance(audio, dict):
        return "audio"
    return "unsupported"


def _positive_float(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None
