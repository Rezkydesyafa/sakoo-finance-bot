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
from app.modules.waha.client import WahaClient, WahaClientError
from app.modules.waha.parser import ParsedWahaMessage


def handle_whatsapp_voice_note(
    *,
    db: Session,
    user_id: int,
    parsed: ParsedWahaMessage,
    waha_client: WahaClient,
    enqueue: VoiceSttEnqueue,
) -> VoiceSttFlowResult | None:
    if parsed.message_type != "audio":
        return None

    if _is_duration_too_long(parsed.duration_seconds):
        return _duration_rejected_result()

    if not parsed.media_url:
        return VoiceSttFlowResult(
            status="download_failed",
            reply_text=(
                "Saya menerima voice note, tetapi URL media dari WAHA tidak tersedia. "
                "Coba kirim ulang voice note-nya."
            ),
            error_message="missing_media_url",
        )

    try:
        downloaded = waha_client.download_media(parsed.media_url)
        media_file = save_media_bytes(
            db,
            user_id=user_id,
            file_type="audio",
            content=downloaded.content,
            original_filename=downloaded.filename or parsed.media_filename,
            mime_type=parsed.media_mimetype or downloaded.content_type,
            source="whatsapp_voice",
        )
    except (WahaClientError, MediaStorageError) as exc:
        return VoiceSttFlowResult(
            status="download_failed",
            reply_text=(
                "Gagal mengunduh atau menyimpan voice note dari WhatsApp. "
                "Coba kirim ulang voice note-nya."
            ),
            error_message=str(exc),
        )

    try:
        job = queue_voice_stt_job(
            db,
            user_id=user_id,
            media_id=media_file.id,
            source="whatsapp",
            enqueue=enqueue,
            duration_seconds=parsed.duration_seconds,
            notify_chat_id=parsed.chat_id,
            notify_session=waha_client.session,
            notify_platform="whatsapp",
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
