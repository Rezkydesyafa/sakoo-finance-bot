from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import BotLog, Transaction, User, UserPlatformAccount, UserPreference
from app.modules.bot.response_templates import format_rupiah
from app.modules.budgets.service import get_budget_for_category, month_bounds
from app.modules.notifications.schemas import (
    NotificationPreferencesResponse,
    NotificationPreferencesUpdate,
)
from app.modules.reports.period import ReportPeriod
from app.modules.reports.service import ReportFilters, build_report_category, build_report_summary
from app.modules.telegram.client import TelegramClient, get_telegram_client
from app.modules.waha.client import WahaClient, get_waha_client

DEFAULT_TIME = time(20, 0)
DEFAULT_TIMEZONE = "Asia/Jakarta"
SUMMARY_TIME = time(8, 0)


def get_preferences(db: Session, user_id: int) -> NotificationPreferencesResponse:
    preference = db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))
    active_channels = list(
        db.scalars(
            select(UserPlatformAccount.platform)
            .where(
                UserPlatformAccount.user_id == user_id,
                UserPlatformAccount.is_active.is_(True),
                UserPlatformAccount.chat_id.is_not(None),
            )
            .order_by(UserPlatformAccount.platform)
        )
    )
    return NotificationPreferencesResponse(
        daily_reminder_enabled=preference.daily_reminder_enabled if preference else False,
        daily_reminder_time=(preference.daily_reminder_time if preference else DEFAULT_TIME).strftime("%H:%M"),
        weekly_summary_enabled=preference.weekly_summary_enabled if preference else False,
        monthly_summary_enabled=preference.monthly_summary_enabled if preference else False,
        budget_alert_enabled=preference.budget_alert_enabled if preference else True,
        timezone=preference.timezone if preference else DEFAULT_TIMEZONE,
        active_channels=active_channels,
    )


def update_preferences(
    db: Session,
    user_id: int,
    payload: NotificationPreferencesUpdate,
) -> NotificationPreferencesResponse:
    preference = db.scalar(select(UserPreference).where(UserPreference.user_id == user_id))
    if preference is None:
        preference = UserPreference(user_id=user_id)
        db.add(preference)
    preference.daily_reminder_enabled = payload.daily_reminder_enabled
    preference.daily_reminder_time = time.fromisoformat(payload.daily_reminder_time)
    preference.weekly_summary_enabled = payload.weekly_summary_enabled
    preference.monthly_summary_enabled = payload.monthly_summary_enabled
    preference.budget_alert_enabled = payload.budget_alert_enabled
    preference.timezone = payload.timezone
    db.commit()
    return get_preferences(db, user_id)


def dispatch_due_notifications(
    db: Session,
    *,
    now_utc: datetime | None = None,
    waha_client: WahaClient | None = None,
    telegram_client: TelegramClient | None = None,
) -> dict[str, int]:
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    preferences = list(
        db.scalars(
            select(UserPreference).where(
                or_(
                    UserPreference.daily_reminder_enabled.is_(True),
                    UserPreference.weekly_summary_enabled.is_(True),
                    UserPreference.monthly_summary_enabled.is_(True),
                )
            )
        )
    )
    result = {"sent": 0, "failed": 0, "skipped": 0}
    for preference in preferences:
        local_now = now.astimezone(ZoneInfo(preference.timezone))
        local_date = local_now.date()
        local_time = local_now.time().replace(tzinfo=None)

        if preference.daily_reminder_enabled and local_time >= preference.daily_reminder_time:
            _merge_counts(
                result,
                _dispatch_daily(
                    db,
                    preference,
                    local_date,
                    waha_client=waha_client,
                    telegram_client=telegram_client,
                ),
            )
        if preference.weekly_summary_enabled and local_date.weekday() == 0 and local_time >= SUMMARY_TIME:
            _merge_counts(
                result,
                _dispatch_weekly(
                    db,
                    preference,
                    local_date,
                    waha_client=waha_client,
                    telegram_client=telegram_client,
                ),
            )
        if preference.monthly_summary_enabled and local_date.day == 1 and local_time >= SUMMARY_TIME:
            _merge_counts(
                result,
                _dispatch_monthly(
                    db,
                    preference,
                    local_date,
                    waha_client=waha_client,
                    telegram_client=telegram_client,
                ),
            )
    return result


def check_budget_notification(
    db: Session,
    *,
    transaction_id: int,
    now_utc: datetime | None = None,
    waha_client: WahaClient | None = None,
    telegram_client: TelegramClient | None = None,
) -> dict[str, int]:
    transaction = db.get(Transaction, transaction_id)
    if (
        transaction is None
        or transaction.type != "expense"
        or transaction.status != "confirmed"
        or transaction.category is None
    ):
        return {"sent": 0, "failed": 0, "skipped": 1}

    preference = db.scalar(
        select(UserPreference).where(UserPreference.user_id == transaction.user_id)
    )
    if preference is not None and not preference.budget_alert_enabled:
        return {"sent": 0, "failed": 0, "skipped": 1}

    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    timezone_name = preference.timezone if preference else DEFAULT_TIMEZONE
    local_today = now.astimezone(ZoneInfo(timezone_name)).date()
    month_start, month_end = month_bounds(local_today)
    if not month_start <= transaction.transaction_date <= month_end:
        return {"sent": 0, "failed": 0, "skipped": 1}

    state = get_budget_for_category(
        db,
        transaction.user_id,
        transaction.category,
        today=local_today,
    )
    if state is None:
        return {"sent": 0, "failed": 0, "skipped": 1}
    period_start, period_end, item = state
    threshold = 100 if item.usage_percentage >= Decimal("100") else 80 if item.usage_percentage >= Decimal("80") else None
    if threshold is None:
        return {"sent": 0, "failed": 0, "skipped": 1}

    user = db.get(User, transaction.user_id)
    style = preference.reply_style if preference else "friendly"
    text = _format_budget(
        style=style,
        first_name=_first_name(user),
        item=item,
        threshold=threshold,
        today=local_today,
        period_end=period_end,
    )
    period_key = period_start.strftime("%Y-%m")
    return _deliver_notification(
        db,
        user_id=transaction.user_id,
        notification_type=f"budget-{threshold}",
        event_id=f"budget-{threshold}:{transaction.user_id}:{item.category_id}:{period_key}",
        period_key=period_key,
        text=text,
        waha_client=waha_client,
        telegram_client=telegram_client,
    )


def _dispatch_daily(
    db: Session,
    preference: UserPreference,
    local_date: date,
    *,
    waha_client: WahaClient | None,
    telegram_client: TelegramClient | None,
) -> dict[str, int]:
    period = ReportPeriod("day", local_date, local_date)
    summary = build_report_summary(db, ReportFilters(preference.user_id, period, limit=1))
    categories = build_report_category(
        db,
        user_id=preference.user_id,
        report_period=period,
        transaction_type="expense",
    )
    user = db.get(User, preference.user_id)
    text = _format_daily(
        style=preference.reply_style,
        first_name=_first_name(user),
        summary=summary,
        top_category=categories.items[0] if categories.items else None,
    )
    return _deliver_notification(
        db,
        user_id=preference.user_id,
        notification_type="daily",
        event_id=f"daily:{preference.user_id}:{local_date.isoformat()}",
        period_key=local_date.isoformat(),
        text=text,
        waha_client=waha_client,
        telegram_client=telegram_client,
    )


def _dispatch_weekly(
    db: Session,
    preference: UserPreference,
    local_date: date,
    *,
    waha_client: WahaClient | None,
    telegram_client: TelegramClient | None,
) -> dict[str, int]:
    period_end = local_date - timedelta(days=1)
    period_start = period_end - timedelta(days=6)
    previous_end = period_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=6)
    iso_year, iso_week, _ = period_start.isocalendar()
    return _dispatch_period_summary(
        db,
        preference,
        kind="weekly",
        period=ReportPeriod("week", period_start, period_end),
        previous=ReportPeriod("week", previous_start, previous_end),
        event_id=f"weekly:{preference.user_id}:{iso_year}-W{iso_week:02d}",
        period_key=f"{iso_year}-W{iso_week:02d}",
        waha_client=waha_client,
        telegram_client=telegram_client,
    )


def _dispatch_monthly(
    db: Session,
    preference: UserPreference,
    local_date: date,
    *,
    waha_client: WahaClient | None,
    telegram_client: TelegramClient | None,
) -> dict[str, int]:
    period_end = local_date - timedelta(days=1)
    period_start = period_end.replace(day=1)
    previous_end = period_start - timedelta(days=1)
    previous_start = previous_end.replace(day=1)
    period_key = period_start.strftime("%Y-%m")
    return _dispatch_period_summary(
        db,
        preference,
        kind="monthly",
        period=ReportPeriod("month", period_start, period_end),
        previous=ReportPeriod("month", previous_start, previous_end),
        event_id=f"monthly:{preference.user_id}:{period_key}",
        period_key=period_key,
        waha_client=waha_client,
        telegram_client=telegram_client,
    )


def _dispatch_period_summary(
    db: Session,
    preference: UserPreference,
    *,
    kind: str,
    period: ReportPeriod,
    previous: ReportPeriod,
    event_id: str,
    period_key: str,
    waha_client: WahaClient | None,
    telegram_client: TelegramClient | None,
) -> dict[str, int]:
    summary = build_report_summary(db, ReportFilters(preference.user_id, period, limit=1))
    if summary.transaction_count == 0:
        return _log_skipped(db, preference.user_id, kind, event_id, period_key)
    previous_summary = build_report_summary(
        db,
        ReportFilters(preference.user_id, previous, limit=1),
    )
    categories = build_report_category(
        db,
        user_id=preference.user_id,
        report_period=period,
        transaction_type="expense",
    )
    user = db.get(User, preference.user_id)
    text = _format_period(
        kind=kind,
        style=preference.reply_style,
        first_name=_first_name(user),
        summary=summary,
        previous_summary=previous_summary,
        top_category=categories.items[0] if categories.items else None,
    )
    return _deliver_notification(
        db,
        user_id=preference.user_id,
        notification_type=kind,
        event_id=event_id,
        period_key=period_key,
        text=text,
        waha_client=waha_client,
        telegram_client=telegram_client,
    )


def _deliver_notification(
    db: Session,
    *,
    user_id: int,
    notification_type: str,
    event_id: str,
    period_key: str,
    text: str,
    waha_client: WahaClient | None,
    telegram_client: TelegramClient | None,
) -> dict[str, int]:
    accounts = list(
        db.scalars(
            select(UserPlatformAccount).where(
                UserPlatformAccount.user_id == user_id,
                UserPlatformAccount.is_active.is_(True),
                UserPlatformAccount.chat_id.is_not(None),
            )
        )
    )
    result = {"sent": 0, "failed": 0, "skipped": 0}
    for account in accounts:
        log = _claim_delivery(
            db,
            user_id=user_id,
            platform=account.platform,
            notification_type=notification_type,
            event_id=event_id,
            period_key=period_key,
            text=text,
        )
        if log is None:
            result["skipped"] += 1
            continue
        try:
            if account.platform == "telegram":
                client = telegram_client or next(get_telegram_client())
                client.send_message(chat_id=str(account.chat_id), text=text)
            else:
                client = waha_client or get_waha_client()
                client.send_text(chat_id=str(account.chat_id), text=text)
        except Exception as exc:
            log.status = "failed"
            log.error_message = str(exc)
            result["failed"] += 1
        else:
            log.status = "sent"
            result["sent"] += 1
        db.commit()
    return result


def _claim_delivery(
    db: Session,
    *,
    user_id: int,
    platform: str,
    notification_type: str,
    event_id: str,
    period_key: str,
    text: str,
) -> BotLog | None:
    if db.scalar(
        select(BotLog.id).where(
            BotLog.platform == platform,
            BotLog.external_event_id == event_id,
        )
    ):
        return None
    log = BotLog(
        user_id=user_id,
        platform=platform,
        message_type=f"notification_{notification_type}",
        raw_message=text,
        parsed_result={"notification_type": notification_type, "period_key": period_key},
        status="sending",
        external_event_id=event_id,
    )
    db.add(log)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None
    return log


def _log_skipped(
    db: Session,
    user_id: int,
    notification_type: str,
    event_id: str,
    period_key: str,
) -> dict[str, int]:
    log = _claim_delivery(
        db,
        user_id=user_id,
        platform="system",
        notification_type=notification_type,
        event_id=event_id,
        period_key=period_key,
        text="",
    )
    if log is None:
        return {"sent": 0, "failed": 0, "skipped": 1}
    log.status = "skipped_no_data"
    log.raw_message = None
    db.commit()
    return {"sent": 0, "failed": 0, "skipped": 1}


def _format_daily(*, style: str, first_name: str, summary: Any, top_category: Any) -> str:
    if summary.transaction_count == 0:
        if style == "short":
            return "Belum ada transaksi hari ini. Balas: makan 25rb."
        if style == "detailed":
            return "Hari ini belum ada transaksi yang tercatat. Agar laporan tetap akurat, balas dengan format seperti: makan 25rb."
        return f"Hai {first_name} 👋\nHari ini belum ada transaksi yang tercatat. Ada yang terlewat? Balas: makan 25rb."
    if summary.expense_count == 0:
        text = f"Pemasukan hari ini sudah tercatat {format_rupiah(summary.total_income)}, tetapi belum ada pengeluaran."
        return f"{text}\nBalas jika ada yang terlewat: makan 25rb."

    top = f" Kategori terbesar: {top_category.category_name} {format_rupiah(top_category.total_amount)}." if top_category else ""
    if style == "short":
        return f"{summary.expense_count} pengeluaran hari ini: {format_rupiah(summary.total_expense)}.{top}\nKetik: lihat transaksi hari ini."
    if style == "detailed":
        return (
            f"Hari ini tercatat {summary.expense_count} pengeluaran dengan total {format_rupiah(summary.total_expense)}."
            f"{top}\nKetik: lihat transaksi hari ini."
        )
    return (
        f"Catatan hari ini sudah rapi ✨\n{summary.expense_count} pengeluaran tercatat, total {format_rupiah(summary.total_expense)}."
        f"{top}\nKetik: lihat transaksi hari ini."
    )


def _format_period(
    *,
    kind: str,
    style: str,
    first_name: str,
    summary: Any,
    previous_summary: Any,
    top_category: Any,
) -> str:
    label = "Minggu lalu" if kind == "weekly" else "Bulan lalu"
    command = "laporan minggu lalu" if kind == "weekly" else "laporan bulan lalu"
    top = f" Kategori terbesar: {top_category.category_name} {format_rupiah(top_category.total_amount)}." if top_category else ""
    comparison = _expense_comparison(summary.total_expense, previous_summary)
    if style == "short":
        return (
            f"{label}: pemasukan {format_rupiah(summary.total_income)}, pengeluaran {format_rupiah(summary.total_expense)}, "
            f"selisih {format_rupiah(summary.net_balance)}.{top}\nKetik: {command}."
        )
    if style == "detailed":
        return (
            f"Ringkasan {label.lower()}:\n"
            f"Pemasukan: {format_rupiah(summary.total_income)}\n"
            f"Pengeluaran: {format_rupiah(summary.total_expense)}\n"
            f"Selisih: {format_rupiah(summary.net_balance)}\n"
            f"Jumlah transaksi: {summary.transaction_count}.{top}"
            f"{comparison}\nKetik: {command}."
        )
    return (
        f"{label}, {first_name} 📊\n"
        f"Dari {summary.transaction_count} transaksi, pemasukanmu {format_rupiah(summary.total_income)} dan "
        f"pengeluaranmu {format_rupiah(summary.total_expense)}. Selisihnya {format_rupiah(summary.net_balance)}."
        f"{top}{comparison}\nKetik: {command}."
    )


def _format_budget(*, style: str, first_name: str, item: Any, threshold: int, today: date, period_end: date) -> str:
    if threshold == 100:
        over = max(item.spent - item.monthly_limit, Decimal("0"))
        base = (
            f"Budget {item.category_name} sudah mencapai {format_rupiah(item.spent)} dari {format_rupiah(item.monthly_limit)}, "
            f"melewati batas sebesar {format_rupiah(over)}."
        )
    else:
        days_left = max((period_end - today).days, 1)
        remaining = max(item.remaining, Decimal("0"))
        daily_limit = remaining / Decimal(days_left)
        base = (
            f"Budget {item.category_name} sudah terpakai {format_rupiah(item.spent)} dari {format_rupiah(item.monthly_limit)}. "
            f"Tersisa {format_rupiah(remaining)} untuk {days_left} hari, sekitar {format_rupiah(daily_limit)} per hari."
        )
    if style == "short":
        return f"{base}\nKetik: lihat budget."
    if style == "detailed":
        return f"{base}\nIni hanya pengingat agar rencana bulanan tetap terlihat. Ketik: lihat budget."
    return f"Hai {first_name}, sedikit kabar soal budgetmu 💡\n{base}\nKetik: lihat budget."


def _expense_comparison(current: Decimal, previous_summary: Any) -> str:
    if previous_summary.transaction_count == 0:
        return ""
    difference = current - previous_summary.total_expense
    if difference == 0:
        return " Pengeluaran sama dengan periode sebelumnya."
    direction = "lebih tinggi" if difference > 0 else "lebih rendah"
    return f" Pengeluaran {format_rupiah(abs(difference))} {direction} dari periode sebelumnya."


def _first_name(user: User | None) -> str:
    if user is None or not user.name.strip():
        return ""
    return user.name.strip().split(" ", 1)[0]


def _merge_counts(target: dict[str, int], source: dict[str, int]) -> None:
    for key in target:
        target[key] += source[key]
