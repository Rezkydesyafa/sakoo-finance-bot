from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Job
from app.modules.jobs.service import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PROCESSING,
)
from app.modules.ocr.client import OcrClient, get_ocr_client
from app.modules.ocr.service import process_receipt_ocr
from app.modules.waha.client import WahaClient, get_waha_client
from app.modules.waha.receipt_ocr import format_receipt_confirmation
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.ping")
def ping() -> str:
    return "pong"


@celery_app.task(name="app.workers.receipt_ocr")
def receipt_ocr_job(
    job_id: int,
    user_id: int,
    media_id: int,
    source: str,
    notify_chat_id: str | None = None,
    notify_session: str | None = None,
) -> dict[str, Any]:
    with SessionLocal() as db:
        return run_receipt_ocr_job(
            db,
            job_id=job_id,
            user_id=user_id,
            media_id=media_id,
            source=source,
            notify_chat_id=notify_chat_id,
            notify_session=notify_session,
        )


def enqueue_receipt_ocr_job(
    *,
    job_id: int,
    user_id: int,
    media_id: int,
    source: str,
    notify_chat_id: str | None = None,
    notify_session: str | None = None,
) -> Any:
    return receipt_ocr_job.delay(
        job_id,
        user_id,
        media_id,
        source,
        notify_chat_id,
        notify_session,
    )


def run_receipt_ocr_job(
    db: Session,
    *,
    job_id: int,
    user_id: int,
    media_id: int,
    source: str,
    ocr_client: OcrClient | None = None,
    waha_client: WahaClient | None = None,
    notify_chat_id: str | None = None,
    notify_session: str | None = None,
) -> dict[str, Any]:
    job = _get_job(db, job_id=job_id, user_id=user_id)
    if job is None:
        return {"status": "not_found", "job_id": job_id}

    job.status = JOB_STATUS_PROCESSING
    job.error_message = None
    db.commit()

    try:
        receipt = process_receipt_ocr(
            db,
            user_id=user_id,
            media_id=media_id,
            ocr_client=ocr_client or get_ocr_client(),
            source=source,
            enforce_rate_limit=False,
            log_usage=False,
        )
        job.status = JOB_STATUS_COMPLETED
        job.result_id = receipt.id
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(job)
    except Exception as exc:
        db.rollback()
        job = _get_job(db, job_id=job_id, user_id=user_id)
        if job is not None:
            job.status = JOB_STATUS_FAILED
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        raise

    try:
        _send_receipt_notification_if_needed(
            receipt=receipt,
            waha_client=waha_client,
            notify_chat_id=notify_chat_id,
            notify_session=notify_session,
        )
    except Exception as exc:
        job.error_message = f"Notification failed: {exc}"
        db.commit()

    return {
        "status": job.status,
        "job_id": job.id,
        "receipt_id": receipt.id,
    }


def _get_job(db: Session, *, job_id: int, user_id: int) -> Job | None:
    job = db.get(Job, job_id)
    if job is None or job.user_id != user_id:
        return None
    return job


def _send_receipt_notification_if_needed(
    *,
    receipt: Any,
    waha_client: WahaClient | None,
    notify_chat_id: str | None,
    notify_session: str | None,
) -> None:
    if not notify_chat_id:
        return
    client = waha_client or get_waha_client()
    client.send_text(
        chat_id=notify_chat_id,
        text=format_receipt_confirmation(receipt),
        session=notify_session,
    )
