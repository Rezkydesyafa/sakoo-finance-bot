from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx

from app.config import get_settings


class TelegramClientError(RuntimeError):
    pass


class TelegramClient:
    def __init__(
        self,
        *,
        bot_token: str,
        base_url: str,
        timeout_seconds: float,
    ) -> None:
        self.bot_token = bot_token
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def send_message(
        self,
        *,
        chat_id: str,
        text: str,
        parse_mode: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        return self._post("sendMessage", payload)

    def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.bot_token:
            raise TelegramClientError("telegram_bot_token_not_configured")

        url = f"{self.base_url}/bot{self.bot_token}/{method}"
        try:
            response = httpx.post(
                url,
                json=payload,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise TelegramClientError(f"telegram_request_failed: {exc}") from exc

        try:
            data = response.json()
        except ValueError as exc:
            raise TelegramClientError("telegram_invalid_json_response") from exc

        if not data.get("ok"):
            description = data.get("description", "unknown_error")
            raise TelegramClientError(f"telegram_api_error: {description}")
        return data


def get_telegram_client() -> Iterator[TelegramClient]:
    settings = get_settings()
    yield TelegramClient(
        bot_token=settings.telegram_bot_token,
        base_url=settings.telegram_base_url,
        timeout_seconds=settings.telegram_timeout_seconds,
    )
