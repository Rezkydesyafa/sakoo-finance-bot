from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from app.models.identity import User
    from app.models.operations import Receipt, VoiceNote

BigIntPk = BigInteger().with_variant(Integer, "sqlite")


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(32), nullable=True)
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    keywords: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    is_default: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    user: Mapped["User | None"] = relationship(back_populates="categories")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="category")
    budgets: Mapped[list["CategoryBudget"]] = relationship(back_populates="category")

    __table_args__ = (
        CheckConstraint(
            "type IN ('income', 'expense', 'both')",
            name="ck_categories_type",
        ),
        UniqueConstraint("user_id", "name", "type", name="uq_categories_user_name_type"),
        Index("ix_categories_user_id", "user_id"),
    )


class CategoryBudget(TimestampMixin, Base):
    __tablename__ = "category_budgets"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=False,
    )
    monthly_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    user: Mapped["User"] = relationship(back_populates="category_budgets")
    category: Mapped["Category"] = relationship(back_populates="budgets")

    __table_args__ = (
        UniqueConstraint("user_id", "category_id", name="uq_category_budgets_user_category"),
        Index("ix_category_budgets_user_id", "user_id"),
    )


class UserPreference(TimestampMixin, Base):
    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reply_style: Mapped[str] = mapped_column(
        String(16),
        default="friendly",
        server_default="friendly",
        nullable=False,
    )
    daily_reminder_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    daily_reminder_time: Mapped[time] = mapped_column(
        Time,
        default=time(20, 0),
        server_default="20:00:00",
        nullable=False,
    )
    weekly_summary_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    monthly_summary_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
    )
    budget_alert_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )
    timezone: Mapped[str] = mapped_column(
        String(32),
        default="Asia/Jakarta",
        server_default="Asia/Jakarta",
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="preference")

    __table_args__ = (
        CheckConstraint(
            "reply_style IN ('friendly', 'detailed', 'short')",
            name="ck_user_preferences_reply_style",
        ),
        CheckConstraint(
            "timezone IN ('Asia/Jakarta', 'Asia/Makassar', 'Asia/Jayapura')",
            name="ck_user_preferences_timezone",
        ),
        UniqueConstraint("user_id", name="uq_user_preferences_user_id"),
    )


class Transaction(TimestampMixin, Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(BigIntPk, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"),
        nullable=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="confirmed",
        server_default="confirmed",
    )

    user: Mapped["User"] = relationship(back_populates="transactions")
    category: Mapped["Category | None"] = relationship(back_populates="transactions")
    receipts: Mapped[list["Receipt"]] = relationship(back_populates="transaction")
    voice_notes: Mapped[list["VoiceNote"]] = relationship(back_populates="transaction")

    @property
    def category_name(self) -> str | None:
        return self.category.name if self.category else None

    __table_args__ = (
        CheckConstraint("type IN ('income', 'expense')", name="ck_transactions_type"),
        CheckConstraint(
            "source IN ('whatsapp_text', 'telegram_text', 'dashboard_manual', "
            "'receipt_ocr', 'voice_note')",
            name="ck_transactions_source",
        ),
        CheckConstraint(
            "status IN ('pending_confirmation', 'confirmed', 'cancelled')",
            name="ck_transactions_status",
        ),
        Index("ix_transactions_user_date", "user_id", "transaction_date"),
        Index("ix_transactions_user_category", "user_id", "category_id"),
        Index("ix_transactions_user_type_date", "user_id", "type", "transaction_date"),
        Index("ix_transactions_user_status_created", "user_id", "status", "created_at"),
        Index(
            "ix_transactions_user_category_date",
            "user_id",
            "category_id",
            "transaction_date",
        ),
    )
