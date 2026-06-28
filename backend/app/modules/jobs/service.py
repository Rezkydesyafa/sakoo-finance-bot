from collections.abc import Callable
from datetime import date
from typing import Any

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Job
from app.modules.media.service import MediaStorageError, resolve_media_file_path
from app.modules.ocr.rate_limit import (
    OcrRateLimitExceeded,
    enforce_ocr_daily_limit,
    log_ocr_usage,
)
from app.modules.ocr.service import ReceiptOcrError, get_receipt_media_file
from app.modules.reports.period import ReportPeriodError, resolve_report_period
from app.modules.stt.service import (
    VoiceSttError,
    get_audio_media_file,
    validate_voice_note_duration,
)


JOB_STATUS_QUEUED = "queued"
JOB_STATUS_PROCESSING = "processing"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"
RECEIPT_OCR_JOB_TYPE = "receipt_ocr"
VOICE_STT_JOB_TYPE = "voice_stt"
REPORT_PDF_JOB_TYPE = "report_pdf"

ReceiptOcrEnqueue = Callable[..., Any]
VoiceSttEnqueue = Callable[..., Any]
ReportPdfEnqueue = Callable[..., Any]


class JobQueueError(Exception):
    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def get_user_job(db: Session, *, user_id: int, job_id: int) -> Job | None:
    return db.scalar(
        select(Job).where(
            Job.id == job_id,
            Job.user_id == user_id,
        )
    )


def queue_receipt_ocr_job(
    db: Session,
    *,
    user_id: int,
    media_id: int,
    source: str,
    enqueue: ReceiptOcrEnqueue,
    notify_chat_id: str | None = None,
    notify_session: str | None = None,
) -> Job:
    try:
        media_file = get_receipt_media_file(db, user_id=user_id, media_id=media_id)
    except ReceiptOcrError as exc:
        raise JobQueueError(exc.detail, exc.status_code) from exc
    settings = get_settings()

    try:
        rate_limit_state = enforce_ocr_daily_limit(
            db,
            user_id=user_id,
            limit=settings.ocr_daily_limit_per_user,
            timezone_name=settings.ocr_rate_limit_timezone,
            source=source,
            media_id=media_file.id,
        )
    except OcrRateLimitExceeded as exc:
        raise JobQueueError(exc.detail, exc.status_code) from exc

    job = Job(
        user_id=user_id,
        job_type=RECEIPT_OCR_JOB_TYPE,
        status=JOB_STATUS_QUEUED,
    )
    db.add(job)
    db.flush()
    log_ocr_usage(
        db,
        user_id=user_id,
        source=source,
        media_id=media_file.id,
        receipt_id=None,
        state=rate_limit_state,
        job_id=job.id,
    )
    db.commit()
    db.refresh(job)

    try:
        enqueue(
            job_id=job.id,
            user_id=user_id,
            media_id=media_file.id,
            source=source,
            notify_chat_id=notify_chat_id,
            notify_session=notify_session,
        )
    except Exception as exc:
        job.status = JOB_STATUS_FAILED
        job.error_message = f"Failed to enqueue job: {exc}"
        db.commit()
        raise JobQueueError(
            "Failed to queue OCR job. Check Celery/Redis worker configuration.",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc

    return job


def queue_voice_stt_job(
    db: Session,
    *,
    user_id: int,
    media_id: int,
    source: str,
    enqueue: VoiceSttEnqueue,
    duration_seconds: float | None = None,
    notify_chat_id: str | None = None,
    notify_session: str | None = None,
    notify_platform: str | None = None,
) -> Job:
    try:
        media_file = get_audio_media_file(db, user_id=user_id, media_id=media_id)
        file_path = resolve_media_file_path(media_file)
        validate_voice_note_duration(
            file_path=file_path,
            mime_type=media_file.mime_type,
            duration_seconds=duration_seconds,
        )
    except (VoiceSttError, MediaStorageError) as exc:
        detail = exc.detail if hasattr(exc, "detail") else str(exc)
        status_code = (
            exc.status_code
            if hasattr(exc, "status_code")
            else status.HTTP_400_BAD_REQUEST
        )
        raise JobQueueError(detail, status_code) from exc

    job = Job(
        user_id=user_id,
        job_type=VOICE_STT_JOB_TYPE,
        status=JOB_STATUS_QUEUED,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        enqueue(
            job_id=job.id,
            user_id=user_id,
            media_id=media_file.id,
            source=source,
            duration_seconds=duration_seconds,
            notify_chat_id=notify_chat_id,
            notify_session=notify_session,
            notify_platform=notify_platform,
        )
    except Exception as exc:
        job.status = JOB_STATUS_FAILED
        job.error_message = f"Failed to enqueue job: {exc}"
        db.commit()
        raise JobQueueError(
            "Failed to queue STT job. Check Celery/Redis worker configuration.",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc

    return job


def queue_report_pdf_job(
    db: Session,
    *,
    user_id: int,
    period: str,
    source: str,
    enqueue: ReportPdfEnqueue,
    anchor_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    notify_chat_id: str | None = None,
    notify_session: str | None = None,
    notify_platform: str | None = None,
) -> Job:
    try:
        report_period = resolve_report_period(
            period=period,
            anchor_date=anchor_date,
            start_date=start_date,
            end_date=end_date,
        )
    except ReportPeriodError as exc:
        raise JobQueueError(exc.detail, exc.status_code) from exc

    job = Job(
        user_id=user_id,
        job_type=REPORT_PDF_JOB_TYPE,
        status=JOB_STATUS_QUEUED,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        enqueue(
            job_id=job.id,
            user_id=user_id,
            period=report_period.report_type,
            source=source,
            anchor_date=anchor_date.isoformat() if anchor_date else None,
            start_date=report_period.period_start.isoformat()
            if report_period.report_type == "custom"
            else None,
            end_date=report_period.period_end.isoformat()
            if report_period.report_type == "custom"
            else None,
            notify_chat_id=notify_chat_id,
            notify_session=notify_session,
            notify_platform=notify_platform,
        )
    except Exception as exc:
        job.status = JOB_STATUS_FAILED
        job.error_message = f"Failed to enqueue job: {exc}"
        db.commit()
        raise JobQueueError(
            "Failed to queue PDF job. Check Celery/Redis worker configuration.",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        ) from exc

    return job


def get_receipt_ocr_enqueue() -> ReceiptOcrEnqueue:
    from app.workers.tasks import enqueue_receipt_ocr_job

    return enqueue_receipt_ocr_job


def get_voice_stt_enqueue() -> VoiceSttEnqueue:
    from app.workers.tasks import enqueue_voice_stt_job

    return enqueue_voice_stt_job


def get_report_pdf_enqueue() -> ReportPdfEnqueue:
    from app.workers.tasks import enqueue_report_pdf_job

    return enqueue_report_pdf_job
