from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from fastapi import status

from app.config import get_settings


class SttClient(Protocol):
    def transcribe(
        self,
        audio_content: bytes,
        *,
        mime_type: str | None = None,
        sample_rate_hertz: int | None = None,
    ) -> "SttResult":
        """Transcribe audio bytes into text."""


@dataclass(frozen=True)
class SttResult:
    text: str
    provider: str = "google_speech_to_text"
    confidence: float | None = None
    raw: dict[str, Any] | None = None


class SttClientError(Exception):
    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_502_BAD_GATEWAY,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class GoogleSpeechToTextClient:
    def __init__(
        self,
        *,
        credentials_path: str | None = None,
        language_code: str = "id-ID",
        enable_automatic_punctuation: bool = True,
        speech_client: Any | None = None,
    ) -> None:
        self.credentials_path = credentials_path
        self.language_code = language_code
        self.enable_automatic_punctuation = enable_automatic_punctuation
        self._client = speech_client

    def transcribe(
        self,
        audio_content: bytes,
        *,
        mime_type: str | None = None,
        sample_rate_hertz: int | None = None,
    ) -> SttResult:
        if not audio_content:
            raise SttClientError("Audio content is empty", status.HTTP_400_BAD_REQUEST)

        client = self._get_client()
        try:
            from google.api_core import exceptions as google_exceptions
            from google.auth import exceptions as auth_exceptions
            from google.cloud import speech
        except ImportError as exc:
            raise SttClientError(
                "Google Speech-to-Text dependency is not installed",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

        config_kwargs: dict[str, Any] = {
            "language_code": self.language_code,
            "enable_automatic_punctuation": self.enable_automatic_punctuation,
        }
        encoding = _resolve_google_audio_encoding(speech, mime_type)
        if encoding is not None:
            config_kwargs["encoding"] = encoding
        if sample_rate_hertz is not None:
            config_kwargs["sample_rate_hertz"] = sample_rate_hertz

        try:
            response = client.recognize(
                config=speech.RecognitionConfig(**config_kwargs),
                audio=speech.RecognitionAudio(content=audio_content),
            )
        except auth_exceptions.DefaultCredentialsError as exc:
            raise SttClientError(
                "Google Speech-to-Text credentials are not configured",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc
        except google_exceptions.ResourceExhausted as exc:
            raise SttClientError(
                "Google Speech-to-Text quota exceeded",
                status.HTTP_503_SERVICE_UNAVAILABLE,
            ) from exc
        except google_exceptions.InvalidArgument as exc:
            raise SttClientError(
                f"Google Speech-to-Text rejected the audio: {exc}",
                status.HTTP_400_BAD_REQUEST,
            ) from exc
        except google_exceptions.GoogleAPICallError as exc:
            raise SttClientError(f"Google Speech-to-Text API error: {exc}") from exc
        except google_exceptions.RetryError as exc:
            raise SttClientError(f"Google Speech-to-Text retry failed: {exc}") from exc

        text, confidence = _extract_transcript_from_response(response)
        return SttResult(
            text=text,
            confidence=confidence,
            raw={
                "provider": "google_speech_to_text",
                "text_length": len(text),
                "result_count": len(getattr(response, "results", []) or []),
                "confidence": confidence,
            },
        )

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client

        try:
            from google.auth import exceptions as auth_exceptions
            from google.cloud import speech
        except ImportError as exc:
            raise SttClientError(
                "Google Speech-to-Text dependency is not installed",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

        try:
            if self.credentials_path:
                credentials_file = Path(self.credentials_path)
                if not credentials_file.is_file():
                    raise SttClientError(
                        "Google Speech-to-Text credentials file is not available",
                        status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
                self._client = speech.SpeechClient.from_service_account_file(
                    str(credentials_file)
                )
            else:
                self._client = speech.SpeechClient()
        except auth_exceptions.DefaultCredentialsError as exc:
            raise SttClientError(
                "Google Speech-to-Text credentials are not configured",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

        return self._client


def get_stt_client() -> SttClient:
    settings = get_settings()
    return GoogleSpeechToTextClient(
        credentials_path=settings.google_application_credentials or None,
        language_code=settings.stt_language_code,
        enable_automatic_punctuation=settings.stt_enable_automatic_punctuation,
    )


def _resolve_google_audio_encoding(speech: Any, mime_type: str | None) -> Any | None:
    normalized_mime_type = _normalize_mime_type(mime_type)
    audio_encoding = speech.RecognitionConfig.AudioEncoding

    if normalized_mime_type in {"audio/wav", "audio/wave", "audio/x-wav", "audio/flac"}:
        return None

    encoding_name_by_mime_type = {
        "audio/ogg": "OGG_OPUS",
        "audio/oga": "OGG_OPUS",
        "audio/opus": "OGG_OPUS",
        "audio/webm": "WEBM_OPUS",
        "audio/mpeg": "MP3",
        "audio/mp3": "MP3",
        "audio/amr": "AMR",
    }
    encoding_name = encoding_name_by_mime_type.get(normalized_mime_type or "")
    if not encoding_name:
        raise SttClientError(
            "Audio MIME type is not supported by Google Speech-to-Text",
            status.HTTP_400_BAD_REQUEST,
        )

    encoding = getattr(audio_encoding, encoding_name, None)
    if encoding is None:
        raise SttClientError(
            f"Google Speech-to-Text encoding {encoding_name} is not available",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    return encoding


def _extract_transcript_from_response(response: Any) -> tuple[str, float | None]:
    transcripts: list[str] = []
    confidences: list[float] = []

    for result in getattr(response, "results", []) or []:
        alternatives = getattr(result, "alternatives", []) or []
        if not alternatives:
            continue
        alternative = alternatives[0]
        transcript = getattr(alternative, "transcript", None)
        if transcript:
            transcripts.append(str(transcript).strip())
        confidence = getattr(alternative, "confidence", None)
        if isinstance(confidence, (float, int)) and confidence > 0:
            confidences.append(float(confidence))

    text = " ".join(item for item in transcripts if item).strip()
    confidence = sum(confidences) / len(confidences) if confidences else None
    return text, confidence


def _normalize_mime_type(mime_type: str | None) -> str | None:
    if not mime_type:
        return None
    return mime_type.split(";", 1)[0].strip().lower() or None
