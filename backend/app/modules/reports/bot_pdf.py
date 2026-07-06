from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.modules.jobs.service import (
    JobQueueError,
    ReportPdfEnqueue,
    queue_report_pdf_job,
)
from app.modules.parser.service import ParsedMessage, parse_message
from app.modules.parser.transaction_text import INTENT_EXPORT_PDF


@dataclass(frozen=True)
class ReportPdfFlowResult:
    status: str
    reply_text: str
    parse_result: ParsedMessage
    period: str
    anchor_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    job_id: int | None = None
    error_message: str | None = None

    def to_log_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reply_text": self.reply_text,
            "parse_result": self.parse_result.to_log_payload(),
            "period": self.period,
            "anchor_date": self.anchor_date.isoformat()
            if self.anchor_date
            else None,
            "start_date": self.start_date.isoformat() if self.start_date else None,
            "end_date": self.end_date.isoformat() if self.end_date else None,
            "job_id": self.job_id,
            "error_message": self.error_message,
        }


def handle_report_pdf_command(
    *,
    db: Session,
    user_id: int,
    text: str,
    platform: str,
    enqueue: ReportPdfEnqueue,
    notify_chat_id: str | None,
    notify_session: str | None = None,
    today: date | None = None,
) -> ReportPdfFlowResult | None:
    parse_result = parse_message(text, source=f"{platform}_text", today=today)
    if parse_result.intent != INTENT_EXPORT_PDF:
        return None

    current_date = today or date.today()
    period, anchor_date, start_date, end_date = _resolve_bot_period(
        parse_result.period,
        current_date,
    )

    try:
        job = queue_report_pdf_job(
            db,
            user_id=user_id,
            period=period,
            anchor_date=anchor_date,
            start_date=start_date,
            end_date=end_date,
            source=f"{platform}_bot",
            enqueue=enqueue,
            notify_chat_id=notify_chat_id,
            notify_session=notify_session,
            notify_platform=platform,
        )
    except JobQueueError as exc:
        return ReportPdfFlowResult(
            status="queue_failed",
            reply_text=(
                "Maaf, permintaan PDF laporan belum bisa diproses. "
                "Coba lagi beberapa saat lagi."
            ),
            parse_result=parse_result,
            period=period,
            anchor_date=anchor_date,
            start_date=start_date,
            end_date=end_date,
            error_message=exc.detail,
        )

    return ReportPdfFlowResult(
        status="queued",
        reply_text=(
            f"Siap, aku buatin export PDF laporan {_format_period_label(parse_result.period)}. "
            f"Permintaan export PDF laporan {_format_period_label(parse_result.period)} "
            "sudah masuk antrean, nanti aku kirim file PDF-nya setelah selesai."
        ),
        parse_result=parse_result,
        period=period,
        anchor_date=anchor_date,
        start_date=start_date,
        end_date=end_date,
        job_id=job.id,
    )


def _resolve_bot_period(
    parsed_period: str | None,
    current_date: date,
) -> tuple[str, date | None, date | None, date | None]:
    if parsed_period == "yesterday":
        return "day", current_date - timedelta(days=1), None, None
    if parsed_period in {"day", "week", "month"}:
        return parsed_period, current_date, None, None
    return "month", current_date, None, None


def _format_period_label(parsed_period: str | None) -> str:
    labels = {
        "day": "hari ini",
        "week": "minggu ini",
        "month": "bulan ini",
        "yesterday": "kemarin",
    }
    return labels.get(parsed_period or "", "bulan ini")
