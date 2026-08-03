from datetime import time
from typing import Literal

from pydantic import BaseModel, field_validator

TimezoneName = Literal["Asia/Jakarta", "Asia/Makassar", "Asia/Jayapura"]
ChannelName = Literal["whatsapp", "telegram"]


class NotificationPreferencesUpdate(BaseModel):
    daily_reminder_enabled: bool
    daily_reminder_time: str
    weekly_summary_enabled: bool
    monthly_summary_enabled: bool
    budget_alert_enabled: bool
    timezone: TimezoneName

    @field_validator("daily_reminder_time")
    @classmethod
    def validate_daily_reminder_time(cls, value: str) -> str:
        if len(value) != 5 or value[2] != ":":
            raise ValueError("daily_reminder_time must use HH:MM")
        try:
            time.fromisoformat(value)
        except ValueError as exc:
            raise ValueError("daily_reminder_time must use HH:MM") from exc
        return value


class NotificationPreferencesResponse(NotificationPreferencesUpdate):
    active_channels: list[ChannelName]
