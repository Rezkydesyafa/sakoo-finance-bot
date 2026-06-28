from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.modules.jobs.service import (
    JobQueueError,
    VoiceSttEnqueue,
    queue_voice_stt_job,
)
from app.modules.media.service import MediaStorageError, save_media_bytes
from app.modules.stt.flow import VoiceSttFlowResult
from app.modules.telegram.client import TelegramClient, TelegramClientError
from app.modules.telegram.parser import ParsedTelegramMessage


def handle_telegram_voice_note(
    *,
    db: Session,
    user_id: int,
    parsed: ParsedTelegramMessage,
    telegram_client: TelegramClient,
    enqueue: VoiceSttEnqueue,
) -> VoiceSttFlowResult | None:
    if parsed.message_type != "audio":
        return None

    if _is_duration_too_long(parsed.duration_seconds):
        return _duration_rejected_result()

    if not parsed.file_id:
        return VoiceSttFlowResult(
            status="download_failed",
            reply_text=(
                "Saya menerima voice note, tetapi file_id dari Telegram tidak tersedia. "
                "Coba kirim ulang voice note-nya."
            ),
            error_message="missing_file_id",
        )

    try:
        downloaded = telegram_client.download_media(
            file_id=parsed.file_id,
            fallback_filename=parsed.file_name,
            fallback_content_type=parsed.mime_type,
        )
        media_file = save_media_bytes(
            db,
            user_id=user_id,
            file_type="audio",
            content=downloaded.content,
            original_filename=downloaded.filename or parsed.file_name,
            mime_type=parsed.mime_type or downloaded.content_type,
            source="telegram_voice",
        )
    except (TelegramClientError, MediaStorageError) as exc:
        return VoiceSttFlowResult(
            status="download_failed",
            reply_text=(
                "Gagal mengunduh atau menyimpan voice note dari Telegram. "
                "Coba kirim ulang voice note-nya."
            ),
            error_message=str(exc),
        )

    try:
        job = queue_voice_stt_job(
            db,
            user_id=user_id,
            media_id=media_file.id,
            source="telegram",
            enqueue=enqueue,
            duration_seconds=parsed.duration_seconds,
            notify_chat_id=parsed.chat_id,
            notify_platform="telegram",
        )
    except JobQueueError as exc:
        if exc.status_code == 413:
            return _duration_rejected_result(
                media_file_id=media_file.id,
                error_message=str(exc),
            )
        return VoiceSttFlowResult(
            status="queue_failed",
            media_file_id=media_file.id,
            reply_text=(
                "Voice note sudah diterima, tetapi job STT gagal masuk antrean. "
                "Coba lagi beberapa saat lagi."
            ),
            error_message=str(exc),
        )

    return VoiceSttFlowResult(
        status="queued",
        media_file_id=media_file.id,
        job_id=job.id,
        reply_text=(
            "Voice note diterima dan masuk antrean transkripsi. "
            "Saya akan kirim hasilnya setelah selesai diproses."
        ),
    )


def _is_duration_too_long(duration_seconds: float | None) -> bool:
    return bool(
        duration_seconds
        and duration_seconds > get_settings().stt_max_duration_seconds
    )


def _duration_rejected_result(
    *,
    media_file_id: int | None = None,
    error_message: str | None = None,
) -> VoiceSttFlowResult:
    max_duration = get_settings().stt_max_duration_seconds
    return VoiceSttFlowResult(
        status="duration_rejected",
        media_file_id=media_file_id,
        reply_text=(
            f"Voice note terlalu panjang. Kirim voice note maksimal {max_duration} detik."
        ),
        error_message=error_message or "voice_note_duration_exceeded",
    )
