from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ParsedWahaMessage:
    event_id: str | None
    event: str
    session: str | None
    message_id: str | None
    chat_id: str | None
    sender_id: str | None
    platform_user_id: str | None
    text: str | None
    message_type: str
    has_media: bool
    media_url: str | None
    media_mimetype: str | None
    media_filename: str | None
    duration_seconds: float | None
    from_me: bool | None
    timestamp: int | str | None

    def to_log_payload(self) -> dict[str, Any]:
        return asdict(self)


def parse_waha_message(data: dict[str, Any]) -> ParsedWahaMessage:
    payload = data.get("payload")
    if not isinstance(payload, dict):
        payload = data

    media = payload.get("media")
    if not isinstance(media, dict):
        media = {}

    data_media = _nested_dict(payload, "_data", "mediaData")

    chat_id = _first_string(
        payload.get("from"),
        payload.get("chatId"),
        _nested_value(payload, "id", "remote"),
        payload.get("to"),
    )
    sender_id = _first_string(
        payload.get("participant"),
        payload.get("author"),
        payload.get("from"),
        chat_id,
    )
    text = _first_string(payload.get("body"), payload.get("text"), payload.get("caption"))
    media_url = _first_string(media.get("url"), data_media.get("url"))
    media_mimetype = _first_string(
        media.get("mimetype"),
        media.get("mimeType"),
        data_media.get("mimetype"),
        data_media.get("mimeType"),
        payload.get("mimetype"),
        payload.get("mimeType"),
    )
    media_filename = _first_string(
        media.get("filename"),
        media.get("fileName"),
        data_media.get("filename"),
        data_media.get("fileName"),
    )
    duration_seconds = _first_float(
        media.get("duration"),
        media.get("seconds"),
        data_media.get("duration"),
        data_media.get("seconds"),
        payload.get("duration"),
        payload.get("seconds"),
    )
    has_media = bool(payload.get("hasMedia") or media or media_url or media_mimetype)

    return ParsedWahaMessage(
        event_id=_first_string(data.get("id"), data.get("eventId")),
        event=str(data.get("event") or payload.get("event") or "message"),
        session=_first_string(data.get("session"), payload.get("session")),
        message_id=_first_string(payload.get("id"), _nested_value(payload, "id", "_serialized")),
        chat_id=chat_id,
        sender_id=sender_id,
        platform_user_id=normalize_whatsapp_id(sender_id or chat_id),
        text=text,
        message_type=_detect_message_type(text=text, has_media=has_media, mimetype=media_mimetype, payload=payload),
        has_media=has_media,
        media_url=media_url,
        media_mimetype=media_mimetype,
        media_filename=media_filename,
        duration_seconds=duration_seconds,
        from_me=payload.get("fromMe") if isinstance(payload.get("fromMe"), bool) else None,
        timestamp=payload.get("timestamp") or data.get("timestamp"),
    )


def whatsapp_identifier_candidates(parsed: ParsedWahaMessage) -> list[str]:
    values = [
        parsed.sender_id,
        parsed.chat_id,
        parsed.platform_user_id,
        normalize_whatsapp_id(parsed.sender_id),
        normalize_whatsapp_id(parsed.chat_id),
    ]
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def normalize_whatsapp_id(value: str | None) -> str | None:
    if not value:
        return None
    return value.split("@", 1)[0].strip() or None


def _detect_message_type(
    *,
    text: str | None,
    has_media: bool,
    mimetype: str | None,
    payload: dict[str, Any],
) -> str:
    message_kind = str(payload.get("type") or payload.get("messageType") or "").lower()
    normalized_mimetype = (mimetype or "").lower()

    if normalized_mimetype.startswith("image/") or message_kind in {"image", "sticker"}:
        return "image"
    if (
        normalized_mimetype.startswith("audio/")
        or message_kind in {"audio", "ptt", "voice"}
        or payload.get("isVoice") is True
    ):
        return "audio"
    if has_media:
        return "file"
    if text:
        return "text"
    return message_kind or "unknown"


def _first_string(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_float(*values: Any) -> float | None:
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            return number
    return None


def _nested_value(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _nested_dict(data: dict[str, Any], *keys: str) -> dict[str, Any]:
    value = _nested_value(data, *keys)
    return value if isinstance(value, dict) else {}
