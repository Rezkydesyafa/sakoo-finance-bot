from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Job, MediaFile, Report, User
from app.modules.jobs.service import (
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
    JOB_STATUS_PROCESSING,
)
from app.modules.media.service import resolve_media_file_path
from app.modules.ocr.client import OcrClient, get_ocr_client
from app.modules.ocr.service import process_receipt_ocr
from app.modules.reports.pdf import (
    PdfRenderer,
    generate_report_pdf,
    get_pdf_renderer,
)
from app.modules.reports.period import resolve_report_period
from app.modules.stt.client import SttClient, get_stt_client
from app.modules.stt.service import format_voice_note_result, process_voice_stt
from app.modules.telegram.client import TelegramClient, get_telegram_client
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
    notify_platform: str | None = None,
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
            notify_platform=notify_platform,
        )


def enqueue_receipt_ocr_job(
    *,
    job_id: int,
    user_id: int,
    media_id: int,
    source: str,
    notify_chat_id: str | None = None,
    notify_session: str | None = None,
    notify_platform: str | None = None,
) -> Any:
    return receipt_ocr_job.delay(
        job_id,
        user_id,
        media_id,
        source,
        notify_chat_id,
        notify_session,
        notify_platform,
    )


@celery_app.task(name="app.workers.voice_stt")
def voice_stt_job(
    job_id: int,
    user_id: int,
    media_id: int,
    source: str,
    duration_seconds: float | None = None,
    notify_chat_id: str | None = None,
    notify_session: str | None = None,
    notify_platform: str | None = None,
) -> dict[str, Any]:
    with SessionLocal() as db:
        return run_voice_stt_job(
            db,
            job_id=job_id,
            user_id=user_id,
            media_id=media_id,
            source=source,
            duration_seconds=duration_seconds,
            notify_chat_id=notify_chat_id,
            notify_session=notify_session,
            notify_platform=notify_platform,
        )


def enqueue_voice_stt_job(
    *,
    job_id: int,
    user_id: int,
    media_id: int,
    source: str,
    duration_seconds: float | None = None,
    notify_chat_id: str | None = None,
    notify_session: str | None = None,
    notify_platform: str | None = None,
) -> Any:
    return voice_stt_job.delay(
        job_id,
        user_id,
        media_id,
        source,
        duration_seconds,
        notify_chat_id,
        notify_session,
        notify_platform,
    )


@celery_app.task(name="app.workers.report_pdf")
def report_pdf_job(
    job_id: int,
    user_id: int,
    period: str,
    source: str,
    anchor_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    notify_chat_id: str | None = None,
    notify_session: str | None = None,
    notify_platform: str | None = None,
) -> dict[str, Any]:
    with SessionLocal() as db:
        return run_report_pdf_job(
            db,
            job_id=job_id,
            user_id=user_id,
            period=period,
            source=source,
            anchor_date=anchor_date,
            start_date=start_date,
            end_date=end_date,
            notify_chat_id=notify_chat_id,
            notify_session=notify_session,
            notify_platform=notify_platform,
        )


def enqueue_report_pdf_job(
    *,
    job_id: int,
    user_id: int,
    period: str,
    source: str,
    anchor_date: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    notify_chat_id: str | None = None,
    notify_session: str | None = None,
    notify_platform: str | None = None,
) -> Any:
    return report_pdf_job.delay(
        job_id,
        user_id,
        period,
        source,
        anchor_date,
        start_date,
        end_date,
        notify_chat_id,
        notify_session,
        notify_platform,
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
    telegram_client: TelegramClient | None = None,
    notify_chat_id: str | None = None,
    notify_session: str | None = None,
    notify_platform: str | None = None,
) -> dict[str, Any]:
    job = _get_job(db, job_id=job_id, user_id=user_id)
    if job is None:
        return {"status": "not_found", "job_id": job_id}

    job.status = JOB_STATUS_PROCESSING
    job.error_message = None
    db.commit()

    try:
        _send_receipt_processing_notification_if_needed(
            waha_client=waha_client,
            telegram_client=telegram_client,
            notify_chat_id=notify_chat_id,
            notify_session=notify_session,
            notify_platform=notify_platform,
        )
    except Exception:
        pass

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
            telegram_client=telegram_client,
            notify_chat_id=notify_chat_id,
            notify_session=notify_session,
            notify_platform=notify_platform,
        )
    except Exception as exc:
        job.error_message = f"Notification failed: {exc}"
        db.commit()

    return {
        "status": job.status,
        "job_id": job.id,
        "receipt_id": receipt.id,
    }


def run_voice_stt_job(
    db: Session,
    *,
    job_id: int,
    user_id: int,
    media_id: int,
    source: str,
    duration_seconds: float | None = None,
    stt_client: SttClient | None = None,
    waha_client: WahaClient | None = None,
    telegram_client: TelegramClient | None = None,
    notify_chat_id: str | None = None,
    notify_session: str | None = None,
    notify_platform: str | None = None,
) -> dict[str, Any]:
    job = _get_job(db, job_id=job_id, user_id=user_id)
    if job is None:
        return {"status": "not_found", "job_id": job_id}

    job.status = JOB_STATUS_PROCESSING
    job.error_message = None
    db.commit()

    try:
        voice_note = process_voice_stt(
            db,
            user_id=user_id,
            media_id=media_id,
            stt_client=stt_client or get_stt_client(),
            source=source,
            duration_seconds=duration_seconds,
        )
        job.status = JOB_STATUS_COMPLETED
        job.result_id = voice_note.id
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
        _send_voice_note_notification_if_needed(
            voice_note=voice_note,
            waha_client=waha_client,
            telegram_client=telegram_client,
            notify_chat_id=notify_chat_id,
            notify_session=notify_session,
            notify_platform=notify_platform,
        )
    except Exception as exc:
        job.error_message = f"Notification failed: {exc}"
        db.commit()

    return {
        "status": job.status,
        "job_id": job.id,
        "voice_note_id": voice_note.id,
    }


def run_report_pdf_job(
    db: Session,
    *,
    job_id: int,
    user_id: int,
    period: str,
    source: str,
    anchor_date: date | str | None = None,
    start_date: date | str | None = None,
    end_date: date | str | None = None,
    renderer: PdfRenderer | None = None,
    waha_client: WahaClient | None = None,
    telegram_client: TelegramClient | None = None,
    notify_chat_id: str | None = None,
    notify_session: str | None = None,
    notify_platform: str | None = None,
) -> dict[str, Any]:
    job = _get_job(db, job_id=job_id, user_id=user_id)
    if job is None:
        return {"status": "not_found", "job_id": job_id}

    user = db.get(User, user_id)
    if user is None:
        job.status = JOB_STATUS_FAILED
        job.error_message = "user_not_found"
        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        return {"status": job.status, "job_id": job.id}

    job.status = JOB_STATUS_PROCESSING
    job.error_message = None
    db.commit()

    try:
        report_period = resolve_report_period(
            period=period,
            anchor_date=_parse_optional_date(anchor_date),
            start_date=_parse_optional_date(start_date),
            end_date=_parse_optional_date(end_date),
        )
        report, media_file = generate_report_pdf(
            db,
            user=user,
            report_period=report_period,
            generated_from=source,
            renderer=renderer or get_pdf_renderer(),
        )
        job.status = JOB_STATUS_COMPLETED
        job.result_id = report.id
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
        try:
            _send_report_pdf_error_if_needed(
                waha_client=waha_client,
                telegram_client=telegram_client,
                notify_chat_id=notify_chat_id,
                notify_session=notify_session,
                notify_platform=notify_platform,
            )
        except Exception as notify_exc:
            if job is not None:
                job.error_message = f"{job.error_message}; Notification failed: {notify_exc}"
                db.commit()
        raise

    try:
        _send_report_pdf_notification_if_needed(
            report=report,
            media_file=media_file,
            waha_client=waha_client,
            telegram_client=telegram_client,
            notify_chat_id=notify_chat_id,
            notify_session=notify_session,
            notify_platform=notify_platform,
        )
    except Exception as exc:
        job.error_message = f"Notification failed: {exc}"
        db.commit()

    return {
        "status": job.status,
        "job_id": job.id,
        "report_id": report.id,
        "media_file_id": media_file.id,
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
    telegram_client: TelegramClient | None,
    notify_chat_id: str | None,
    notify_session: str | None,
    notify_platform: str | None,
) -> None:
    if not notify_chat_id:
        return
    text = format_receipt_confirmation(receipt)
    if notify_platform == "telegram":
        client = telegram_client or next(get_telegram_client())
        client.send_message(chat_id=notify_chat_id, text=text)
        return

    client = waha_client or get_waha_client()
    client.send_text(
        chat_id=notify_chat_id,
        text=text,
        session=notify_session,
    )


def _send_receipt_processing_notification_if_needed(
    *,
    waha_client: WahaClient | None,
    telegram_client: TelegramClient | None,
    notify_chat_id: str | None,
    notify_session: str | None,
    notify_platform: str | None,
) -> None:
    if not notify_chat_id:
        return
    text = (
        "Sedang membaca struk...\n"
        "[==>     ] OCR berjalan\n"
        "Tunggu sebentar, aku cek total dan tanggalnya."
    )
    if notify_platform == "telegram":
        client = telegram_client or next(get_telegram_client())
        client.send_message(chat_id=notify_chat_id, text=text)
        return

    client = waha_client or get_waha_client()
    client.send_text(
        chat_id=notify_chat_id,
        text=text,
        session=notify_session,
    )


def _send_voice_note_notification_if_needed(
    *,
    voice_note: Any,
    waha_client: WahaClient | None,
    telegram_client: TelegramClient | None,
    notify_chat_id: str | None,
    notify_session: str | None,
    notify_platform: str | None,
) -> None:
    if not notify_chat_id:
        return

    text = format_voice_note_result(voice_note)
    if notify_platform == "telegram":
        client = telegram_client or next(get_telegram_client())
        client.send_message(chat_id=notify_chat_id, text=text)
        return

    client = waha_client or get_waha_client()
    client.send_text(
        chat_id=notify_chat_id,
        text=text,
        session=notify_session,
    )


def _send_report_pdf_notification_if_needed(
    *,
    report: Report,
    media_file: MediaFile,
    waha_client: WahaClient | None,
    telegram_client: TelegramClient | None,
    notify_chat_id: str | None,
    notify_session: str | None,
    notify_platform: str | None,
) -> None:
    if not notify_chat_id:
        return

    file_path = resolve_media_file_path(media_file)
    file_content = file_path.read_bytes()
    filename = media_file.original_filename or file_path.name
    caption = _format_report_pdf_caption(report)

    if notify_platform == "telegram":
        client = telegram_client or next(get_telegram_client())
        client.send_document(
            chat_id=notify_chat_id,
            file_content=file_content,
            filename=filename,
            caption=caption,
        )
        return

    client = waha_client or get_waha_client()
    client.send_file(
        chat_id=notify_chat_id,
        filename=filename,
        mimetype=media_file.mime_type or "application/pdf",
        file_data=file_content,
        caption=caption,
        session=notify_session,
    )


def _send_report_pdf_error_if_needed(
    *,
    waha_client: WahaClient | None,
    telegram_client: TelegramClient | None,
    notify_chat_id: str | None,
    notify_session: str | None,
    notify_platform: str | None,
) -> None:
    if not notify_chat_id:
        return

    text = (
        "Maaf, PDF laporan gagal dibuat. "
        "Coba lagi beberapa saat lagi atau gunakan periode yang berbeda."
    )
    if notify_platform == "telegram":
        client = telegram_client or next(get_telegram_client())
        client.send_message(chat_id=notify_chat_id, text=text)
        return

    client = waha_client or get_waha_client()
    client.send_text(
        chat_id=notify_chat_id,
        text=text,
        session=notify_session,
    )


def _format_report_pdf_caption(report: Report) -> str:
    return (
        "Laporan PDF siap. "
        f"Periode {report.period_start.isoformat()} sampai "
        f"{report.period_end.isoformat()}."
    )


def _parse_optional_date(value: date | str | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    return date.fromisoformat(value)
