from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.modules.auth.dependencies import get_current_user
from app.modules.reports.pdf import (
    PdfRenderer,
    ReportPdfError,
    generate_report_pdf,
    get_pdf_renderer,
)
from app.modules.reports.period import ReportPeriodError, resolve_report_period
from app.modules.reports.schemas import (
    ReportCategoryResponse,
    ReportPdfGenerateRequest,
    ReportPdfGenerateResponse,
    ReportSummaryResponse,
)
from app.modules.reports.service import (
    ReportFilters,
    build_report_category,
    build_report_summary,
)


router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/summary", response_model=ReportSummaryResponse)
def get_report_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    period: Annotated[str, Query(pattern="^(day|week|month|custom)$")] = "month",
    anchor_date: Annotated[date | None, Query(alias="date")] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReportSummaryResponse:
    report_period = _resolve_period(
        period=period,
        anchor_date=anchor_date,
        start_date=start_date,
        end_date=end_date,
    )
    return build_report_summary(
        db,
        ReportFilters(
            user_id=current_user.id,
            report_period=report_period,
            limit=limit,
            offset=offset,
        ),
    )


@router.get("/category", response_model=ReportCategoryResponse)
def get_report_category(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    period: Annotated[str, Query(pattern="^(day|week|month|custom)$")] = "month",
    anchor_date: Annotated[date | None, Query(alias="date")] = None,
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    transaction_type: Annotated[
        str | None,
        Query(alias="type", pattern="^(income|expense)$"),
    ] = None,
) -> ReportCategoryResponse:
    report_period = _resolve_period(
        period=period,
        anchor_date=anchor_date,
        start_date=start_date,
        end_date=end_date,
    )
    return build_report_category(
        db,
        user_id=current_user.id,
        report_period=report_period,
        transaction_type=transaction_type,
    )


@router.post(
    "/pdf/generate",
    response_model=ReportPdfGenerateResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_report_pdf_endpoint(
    payload: ReportPdfGenerateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    renderer: Annotated[PdfRenderer, Depends(get_pdf_renderer)],
) -> ReportPdfGenerateResponse:
    report_period = _resolve_period(
        period=payload.period,
        anchor_date=payload.anchor_date,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    try:
        report, media_file = generate_report_pdf(
            db,
            user=current_user,
            report_period=report_period,
            generated_from=payload.generated_from,
            renderer=renderer,
        )
    except ReportPdfError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return ReportPdfGenerateResponse(
        report=report,
        file=media_file,
        download_url=f"/api/media/{media_file.id}/download",
    )


def _resolve_period(
    *,
    period: str,
    anchor_date: date | None,
    start_date: date | None,
    end_date: date | None,
):
    try:
        return resolve_report_period(
            period=period,
            anchor_date=anchor_date,
            start_date=start_date,
            end_date=end_date,
        )
    except ReportPeriodError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
