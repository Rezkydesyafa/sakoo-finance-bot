from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from fastapi import status
from sqlalchemy.orm import Session

from app.models import MediaFile, Report, User
from app.modules.media.service import MediaStorageError, save_media_bytes
from app.modules.reports.pdf_template import render_report_pdf_html
from app.modules.reports.period import ReportPeriod
from app.modules.reports.service import (
    ReportFilters,
    build_report_category,
    build_report_summary,
)


class PdfRenderer(Protocol):
    def render_html(self, html: str) -> bytes:
        """Render HTML into PDF bytes."""


class ReportPdfError(Exception):
    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class WeasyPrintPdfRenderer:
    def render_html(self, html: str) -> bytes:
        try:
            from weasyprint import HTML
        except (ImportError, OSError) as exc:
            raise ReportPdfError(
                "WeasyPrint dependency or native libraries are not available",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
            ) from exc

        try:
            return HTML(string=html).write_pdf()
        except Exception as exc:
            raise ReportPdfError(f"Failed to render PDF: {exc}") from exc


def get_pdf_renderer() -> PdfRenderer:
    return WeasyPrintPdfRenderer()


def generate_report_pdf(
    db: Session,
    *,
    user: User,
    report_period: ReportPeriod,
    generated_from: str,
    renderer: PdfRenderer,
    transaction_limit: int = 1000,
) -> tuple[Report, MediaFile]:
    report = Report(
        user_id=user.id,
        period_start=report_period.period_start,
        period_end=report_period.period_end,
        report_type=report_period.report_type,
        generated_from=generated_from,
        status="processing",
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    try:
        summary = build_report_summary(
            db,
            ReportFilters(
                user_id=user.id,
                report_period=report_period,
                limit=transaction_limit,
                offset=0,
            ),
        )
        expense_categories = build_report_category(
            db,
            user_id=user.id,
            report_period=report_period,
            transaction_type="expense",
        )
        income_categories = build_report_category(
            db,
            user_id=user.id,
            report_period=report_period,
            transaction_type="income",
        )
        html = render_report_pdf_html(
            user_name=user.name,
            summary=summary,
            expense_categories=expense_categories,
            income_categories=income_categories,
            generated_at=datetime.now(timezone.utc),
        )
        pdf_content = renderer.render_html(html)
        media_file = save_media_bytes(
            db,
            user_id=user.id,
            file_type="pdf",
            content=pdf_content,
            original_filename=_report_filename(report_period),
            mime_type="application/pdf",
            source="report_pdf",
        )

        report.file_id = media_file.id
        report.status = "completed"
        db.commit()
        db.refresh(report)
        db.refresh(media_file)
        return report, media_file
    except (MediaStorageError, ReportPdfError) as exc:
        _mark_report_failed(db, report)
        detail = exc.detail if hasattr(exc, "detail") else str(exc)
        status_code = (
            exc.status_code
            if hasattr(exc, "status_code")
            else status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        raise ReportPdfError(detail, status_code) from exc
    except Exception as exc:
        _mark_report_failed(db, report)
        raise ReportPdfError(f"Failed to generate report PDF: {exc}") from exc


def _mark_report_failed(db: Session, report: Report) -> None:
    report.status = "failed"
    db.commit()


def _report_filename(report_period: ReportPeriod) -> str:
    return (
        "laporan-keuangan-"
        f"{report_period.report_type}-"
        f"{report_period.period_start.isoformat()}-"
        f"{report_period.period_end.isoformat()}.pdf"
    )
