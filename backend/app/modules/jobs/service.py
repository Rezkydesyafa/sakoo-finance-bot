from collections.abc import Callable
from typing import Any

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Job
from app.modules.ocr.rate_limit import (
    OcrRateLimitExceeded,
    enforce_ocr_daily_limit,
    log_ocr_usage,
)
from app.modules.ocr.service import ReceiptOcrError, get_receipt_media_file


JOB_STATUS_QUEUED = "queued"
JOB_STATUS_PROCESSING = "processing"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"
RECEIPT_OCR_JOB_TYPE = "receipt_ocr"

ReceiptOcrEnqueue = Callable[..., Any]


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


def get_receipt_ocr_enqueue() -> ReceiptOcrEnqueue:
    from app.workers.tasks import enqueue_receipt_ocr_job

    return enqueue_receipt_ocr_job
