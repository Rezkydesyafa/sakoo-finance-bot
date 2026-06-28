from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.config import get_settings


class TelegramClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class DownloadedTelegramFile:
    content: bytes
    content_type: str | None
    filename: str | None


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

    def send_document(
        self,
        *,
        chat_id: str,
        file_content: bytes,
        filename: str,
        caption: str | None = None,
        parse_mode: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"chat_id": chat_id}
        if caption:
            payload["caption"] = caption
        if parse_mode:
            payload["parse_mode"] = parse_mode
        files = {
            "document": (
                filename,
                file_content,
                "application/pdf",
            )
        }
        return self._post_multipart("sendDocument", payload, files)

    def get_file(self, *, file_id: str) -> dict[str, Any]:
        data = self._post("getFile", {"file_id": file_id})
        result = data.get("result")
        if not isinstance(result, dict):
            raise TelegramClientError("telegram_invalid_get_file_response")
        return result

    def download_media(
        self,
        *,
        file_id: str,
        fallback_filename: str | None = None,
        fallback_content_type: str | None = None,
    ) -> DownloadedTelegramFile:
        file_info = self.get_file(file_id=file_id)
        file_path = file_info.get("file_path")
        if not isinstance(file_path, str) or not file_path:
            raise TelegramClientError("telegram_file_path_missing")

        response = self._get_file(file_path)
        filename = fallback_filename or Path(file_path).name or None
        return DownloadedTelegramFile(
            content=response.content,
            content_type=response.headers.get("content-type") or fallback_content_type,
            filename=filename,
        )

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

    def _post_multipart(
        self,
        method: str,
        payload: dict[str, Any],
        files: dict[str, tuple[str, bytes, str]],
    ) -> dict[str, Any]:
        if not self.bot_token:
            raise TelegramClientError("telegram_bot_token_not_configured")

        url = f"{self.base_url}/bot{self.bot_token}/{method}"
        try:
            response = httpx.post(
                url,
                data=payload,
                files=files,
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

    def _get_file(self, file_path: str) -> httpx.Response:
        if not self.bot_token:
            raise TelegramClientError("telegram_bot_token_not_configured")

        url = f"{self.base_url}/file/bot{self.bot_token}/{file_path.lstrip('/')}"
        try:
            response = httpx.get(url, timeout=self.timeout_seconds)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise TelegramClientError(f"telegram_file_download_failed: {exc}") from exc
        return response


def get_telegram_client() -> Iterator[TelegramClient]:
    settings = get_settings()
    yield TelegramClient(
        bot_token=settings.telegram_bot_token,
        base_url=settings.telegram_base_url,
        timeout_seconds=settings.telegram_timeout_seconds,
    )
