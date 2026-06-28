from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from fastapi import status

from app.config import get_settings


class OcrClient(Protocol):
    def extract_text(self, image_content: bytes) -> "OcrResult":
        """Extract text from image bytes."""


@dataclass(frozen=True)
class OcrResult:
    text: str
    provider: str = "google_vision"
    raw: dict[str, Any] | None = None


class OcrClientError(Exception):
    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_502_BAD_GATEWAY,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class GoogleVisionOcrClient:
    def __init__(
        self,
        *,
        credentials_path: str | None = None,
        image_annotator_client: Any | None = None,
    ) -> None:
        self.credentials_path = credentials_path
        self._client = image_annotator_client

    def extract_text(self, image_content: bytes) -> OcrResult:
        if not image_content:
            raise OcrClientError("Image content is empty", status.HTTP_400_BAD_REQUEST)

        client = self._get_client()
        try:
            from google.api_core import exceptions as google_exceptions
            from google.auth import exceptions as auth_exceptions
            from google.cloud import vision
        except ImportError as exc:
            raise OcrClientError(
                "Google Vision dependency is not installed",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

        try:
            response = client.text_detection(image=vision.Image(content=image_content))
        except auth_exceptions.DefaultCredentialsError as exc:
            raise OcrClientError(
                "Google Vision credentials are not configured",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc
        except google_exceptions.ResourceExhausted as exc:
            raise OcrClientError(
                "Google Vision quota exceeded",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from exc
        except google_exceptions.GoogleAPICallError as exc:
            raise OcrClientError(f"Google Vision API error: {exc}") from exc
        except google_exceptions.RetryError as exc:
            raise OcrClientError(f"Google Vision retry failed: {exc}") from exc

        error_message = getattr(getattr(response, "error", None), "message", "")
        if error_message:
            raise OcrClientError(f"Google Vision API error: {error_message}")

        text = _extract_text_from_response(response)
        return OcrResult(
            text=text,
            raw={
                "provider": "google_vision",
                "text_length": len(text),
                "annotation_count": len(getattr(response, "text_annotations", []) or []),
            },
        )

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from google.auth import exceptions as auth_exceptions
            from google.cloud import vision
        except ImportError as exc:
            raise OcrClientError(
                "Google Vision dependency is not installed",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

        try:
            if self.credentials_path:
                credentials_file = Path(self.credentials_path)
                if not credentials_file.is_file():
                    raise OcrClientError(
                        "Google Vision credentials file is not available",
                        status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
                self._client = vision.ImageAnnotatorClient.from_service_account_file(
                    str(credentials_file)
                )
            else:
                self._client = vision.ImageAnnotatorClient()
        except auth_exceptions.DefaultCredentialsError as exc:
            raise OcrClientError(
                "Google Vision credentials are not configured",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

        return self._client


def get_ocr_client() -> OcrClient:
    settings = get_settings()
    return GoogleVisionOcrClient(
        credentials_path=settings.google_application_credentials or None
    )


def _extract_text_from_response(response: Any) -> str:
    full_text_annotation = getattr(response, "full_text_annotation", None)
    full_text = getattr(full_text_annotation, "text", None)
    if full_text:
        return str(full_text).strip()

    text_annotations = getattr(response, "text_annotations", None) or []
    if text_annotations:
        description = getattr(text_annotations[0], "description", None)
        if description:
            return str(description).strip()

    return ""
