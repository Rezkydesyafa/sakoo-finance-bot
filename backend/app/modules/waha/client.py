from base64 import b64encode
from dataclasses import dataclass
from pathlib import PurePath
from typing import Any

import httpx

from app.config import get_settings


class WahaClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


@dataclass(frozen=True)
class DownloadedMedia:
    content: bytes
    content_type: str | None
    filename: str | None


class WahaClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        session: str,
        timeout_seconds: float,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = session
        self.timeout_seconds = timeout_seconds
        self._client = http_client or httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
        )

    def send_text(
        self,
        *,
        chat_id: str,
        text: str,
        session: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/sendText",
            json={
                "session": session or self.session,
                "chatId": chat_id,
                "text": text,
            },
        )

    def send_file(
        self,
        *,
        chat_id: str,
        filename: str,
        mimetype: str = "application/pdf",
        file_url: str | None = None,
        file_data: bytes | str | None = None,
        caption: str | None = None,
        session: str | None = None,
    ) -> dict[str, Any]:
        if bool(file_url) == bool(file_data):
            raise ValueError("Exactly one of file_url or file_data must be provided.")

        file_payload: dict[str, str] = {
            "mimetype": mimetype,
            "filename": filename,
        }
        if file_url:
            file_payload["url"] = file_url
        elif isinstance(file_data, bytes):
            file_payload["data"] = b64encode(file_data).decode("ascii")
        elif isinstance(file_data, str):
            file_payload["data"] = file_data

        payload: dict[str, Any] = {
            "session": session or self.session,
            "chatId": chat_id,
            "file": file_payload,
        }
        if caption:
            payload["caption"] = caption

        return self._request("POST", "/api/sendFile", json=payload)

    def download_media(self, media_url: str) -> DownloadedMedia:
        response = self._raw_request("GET", media_url)
        return DownloadedMedia(
            content=response.content,
            content_type=response.headers.get("content-type"),
            filename=_filename_from_url(str(response.url)),
        )

    def _request(self, method: str, url: str, **kwargs: Any) -> dict[str, Any]:
        response = self._raw_request(method, url, **kwargs)
        if not response.content:
            return {}
        try:
            data = response.json()
        except ValueError:
            return {"content": response.text}
        return data if isinstance(data, dict) else {"data": data}

    def _raw_request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self._client.request(method, url, headers=self._headers(), **kwargs)
        except httpx.TimeoutException as exc:
            raise WahaClientError("WAHA request timed out.") from exc
        except httpx.RequestError as exc:
            raise WahaClientError(f"WAHA request failed: {exc}") from exc

        if response.is_error:
            raise WahaClientError(
                f"WAHA returned HTTP {response.status_code}.",
                status_code=response.status_code,
                response_body=response.text,
            )
        return response

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        return headers


def get_waha_client() -> WahaClient:
    settings = get_settings()
    return WahaClient(
        base_url=settings.waha_base_url,
        api_key=settings.waha_api_key,
        session=settings.waha_session_name,
        timeout_seconds=settings.waha_timeout_seconds,
    )


def _filename_from_url(url: str) -> str | None:
    filename = PurePath(httpx.URL(url).path).name
    return filename or None
