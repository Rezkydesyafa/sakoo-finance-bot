"""Compatibility exports for database models grouped by domain."""

from app.models.base import TimestampMixin
from app.models.finance import Category, CategoryBudget, Transaction, UserPreference
from app.models.identity import AccountLinkingCode, User, UserPlatformAccount
from app.models.operations import BotLog, Job, MediaFile, Receipt, Report, VoiceNote

__all__ = [
    "TimestampMixin",
    "User",
    "UserPlatformAccount",
    "AccountLinkingCode",
    "Category",
    "CategoryBudget",
    "UserPreference",
    "Transaction",
    "MediaFile",
    "Receipt",
    "VoiceNote",
    "Report",
    "Job",
    "BotLog",
]
