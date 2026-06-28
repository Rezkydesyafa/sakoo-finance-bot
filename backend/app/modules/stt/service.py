from __future__ import annotations

from pathlib import Path

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import MediaFile, VoiceNote
from app.modules.media.service import (
    MediaStorageError,
    get_user_media_file,
    resolve_media_file_path,
)
from app.modules.stt.audio import AudioMetadata, probe_audio_metadata
from app.modules.stt.client import SttClient, SttClientError
from app.modules.transactions.service import handle_text_transaction


class VoiceSttError(Exception):
    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def process_voice_stt(
    db: Session,
    *,
    user_id: int,
    media_id: int,
    stt_client: SttClient,
    source: str = "dashboard",
    duration_seconds: float | None = None,
) -> VoiceNote:
    media_file = get_audio_media_file(db, user_id=user_id, media_id=media_id)
    voice_note = _get_or_create_voice_note(
        db,
        user_id=user_id,
        media_file_id=media_file.id,
    )

    try:
        file_path = resolve_media_file_path(media_file)
        metadata = validate_voice_note_duration(
            file_path=file_path,
            mime_type=media_file.mime_type,
            duration_seconds=duration_seconds,
        )
    except (MediaStorageError, VoiceSttError) as exc:
        _mark_voice_note_status(db, voice_note, "rejected")
        if isinstance(exc, MediaStorageError):
            raise VoiceSttError(exc.detail, exc.status_code) from exc
        raise

    audio_content = file_path.read_bytes()
    try:
        result = stt_client.transcribe(
            audio_content,
            mime_type=media_file.mime_type,
            sample_rate_hertz=metadata.sample_rate_hertz,
        )
    except SttClientError:
        _mark_voice_note_status(db, voice_note, "error")
        raise

    transcript = result.text.strip()
    voice_note.transcript_text = transcript or None
    voice_note.stt_provider = result.provider

    if not transcript:
        voice_note.status = "manual_input_required"
        db.commit()
        db.refresh(voice_note)
        return voice_note

    transaction_result = handle_text_transaction(
        db=db,
        user_id=user_id,
        text=transcript,
        source="voice_note",
    )
    voice_note.transaction_id = transaction_result.transaction_id
    voice_note.status = (
        "needs_confirmation"
        if transaction_result.status == "needs_confirmation"
        else "processed"
    )
    db.commit()
    db.refresh(voice_note)
    return voice_note


def get_audio_media_file(db: Session, *, user_id: int, media_id: int) -> MediaFile:
    media_file = get_user_media_file(db, user_id=user_id, media_id=media_id)
    if media_file is None:
        raise VoiceSttError("Audio media file not found", status.HTTP_404_NOT_FOUND)

    if media_file.file_type != "audio":
        raise VoiceSttError(
            "Media file is not audio",
            status.HTTP_400_BAD_REQUEST,
        )

    if not (media_file.mime_type or "").startswith("audio/"):
        raise VoiceSttError(
            "Audio media file must have an audio/* MIME type",
            status.HTTP_400_BAD_REQUEST,
        )

    return media_file


def validate_voice_note_duration(
    *,
    file_path: Path,
    mime_type: str | None,
    duration_seconds: float | None = None,
) -> AudioMetadata:
    settings = get_settings()
    known_duration = _positive_float(duration_seconds)
    metadata = probe_audio_metadata(file_path, mime_type=mime_type)
    durations = [
        item
        for item in (known_duration, metadata.duration_seconds)
        if item is not None
    ]
    actual_duration = max(durations) if durations else None

    if actual_duration is None:
        raise VoiceSttError(
            "Audio duration could not be determined",
            status.HTTP_400_BAD_REQUEST,
        )

    if actual_duration > settings.stt_max_duration_seconds:
        raise VoiceSttError(
            f"Voice note duration exceeds {settings.stt_max_duration_seconds} seconds",
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    return AudioMetadata(
        duration_seconds=actual_duration,
        sample_rate_hertz=metadata.sample_rate_hertz,
    )


def format_voice_note_result(voice_note: VoiceNote) -> str:
    transcript = voice_note.transcript_text or ""
    if voice_note.status == "manual_input_required":
        return (
            "Voice note selesai diproses, tetapi transkrip belum terbaca jelas. "
            "Coba kirim ulang voice note yang lebih jelas dan singkat."
        )
    if voice_note.status == "needs_confirmation":
        return (
            f"Voice note selesai ditranskrip: \"{transcript}\". "
            "Saya belum yakin membaca transaksinya. Kirim ulang dengan format lebih jelas, "
            "contoh: beli kopi 18 ribu."
        )
    if voice_note.transaction_id:
        return (
            f"Voice note selesai ditranskrip: \"{transcript}\". "
            "Transaksi sudah diproses dari transkrip tersebut."
        )
    return f"Voice note selesai ditranskrip: \"{transcript}\"."


def _get_or_create_voice_note(
    db: Session,
    *,
    user_id: int,
    media_file_id: int,
) -> VoiceNote:
    voice_note = db.scalar(
        select(VoiceNote).where(
            VoiceNote.user_id == user_id,
            VoiceNote.media_file_id == media_file_id,
        )
    )
    if voice_note is not None:
        return voice_note

    voice_note = VoiceNote(
        user_id=user_id,
        media_file_id=media_file_id,
        status="pending",
    )
    db.add(voice_note)
    db.flush()
    return voice_note


def _mark_voice_note_status(db: Session, voice_note: VoiceNote, status_value: str) -> None:
    voice_note.status = status_value
    db.commit()


def _positive_float(value: float | int | str | None) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None
