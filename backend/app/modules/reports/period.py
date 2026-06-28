from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

from fastapi import status


SUPPORTED_REPORT_PERIODS = {"day", "week", "month", "custom"}


@dataclass(frozen=True)
class ReportPeriod:
    report_type: str
    period_start: date
    period_end: date


class ReportPeriodError(Exception):
    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def resolve_report_period(
    *,
    period: str,
    anchor_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> ReportPeriod:
    normalized_period = period.strip().lower()
    if normalized_period not in SUPPORTED_REPORT_PERIODS:
        raise ReportPeriodError(
            "period must be one of: day, week, month, custom",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    if normalized_period == "custom":
        if start_date is None or end_date is None:
            raise ReportPeriodError(
                "start_date and end_date are required for custom period",
                status.HTTP_400_BAD_REQUEST,
            )
        if start_date > end_date:
            raise ReportPeriodError(
                "start_date cannot be after end_date",
                status.HTTP_400_BAD_REQUEST,
            )
        return ReportPeriod(
            report_type=normalized_period,
            period_start=start_date,
            period_end=end_date,
        )

    current_date = anchor_date or date.today()
    if normalized_period == "day":
        period_start = current_date
        period_end = current_date
    elif normalized_period == "week":
        period_start = current_date - timedelta(days=current_date.weekday())
        period_end = period_start + timedelta(days=6)
    else:
        last_day = calendar.monthrange(current_date.year, current_date.month)[1]
        period_start = current_date.replace(day=1)
        period_end = current_date.replace(day=last_day)

    return ReportPeriod(
        report_type=normalized_period,
        period_start=period_start,
        period_end=period_end,
    )
