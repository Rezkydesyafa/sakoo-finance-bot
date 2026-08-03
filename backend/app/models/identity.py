from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.finance import Category, CategoryBudget, Transaction, UserPreference
    from app.models.operations import BotLog, Job, MediaFile, Receipt, Report, VoiceNote

BigIntPk = BigInteger().with_variant(Integer, "sqlite")


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)

    platform_accounts: Mapped[list["UserPlatformAccount"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    linking_codes: Mapped[list["AccountLinkingCode"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    media_files: Mapped[list["MediaFile"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    receipts: Mapped[list["Receipt"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    voice_notes: Mapped[list["VoiceNote"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    reports: Mapped[list["Report"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    jobs: Mapped[list["Job"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    preference: Mapped["UserPreference | None"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    category_budgets: Mapped[list["CategoryBudget"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    categories: Mapped[list["Category"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    bot_logs: Mapped[list["BotLog"]] = relationship(back_populates="user")

    __table_args__ = (
        Index("ix_users_email", "email", unique=True),
        Index("ix_users_phone_number", "phone_number", unique=True),
    )


class UserPlatformAccount(Base):
    __tablename__ = "user_platform_accounts"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    platform: Mapped[str] = mapped_column(String(32), nullable=False)
    platform_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    chat_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        server_default="true",
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="platform_accounts")

    __table_args__ = (
        CheckConstraint(
            "platform IN ('whatsapp', 'telegram')",
            name="ck_user_platform_accounts_platform",
        ),
        UniqueConstraint(
            "user_id",
            "platform",
            name="uq_user_platform_accounts_user_platform",
        ),
        UniqueConstraint(
            "platform",
            "platform_user_id",
            name="uq_user_platform_accounts_platform_user_id",
        ),
    )


class AccountLinkingCode(Base):
    __tablename__ = "account_linking_codes"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    expired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="linking_codes")

    __table_args__ = (
        Index("ix_account_linking_codes_code", "code", unique=True),
        Index("ix_account_linking_codes_user_id", "user_id"),
    )
