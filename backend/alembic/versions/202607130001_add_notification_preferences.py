"""add notification preferences

Revision ID: 202607130001
Revises: 202607070005
Create Date: 2026-07-13 00:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "202607130001"
down_revision: str | None = "202607070005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("user_preferences") as batch_op:
        batch_op.add_column(
            sa.Column("daily_reminder_enabled", sa.Boolean(), server_default="false", nullable=False)
        )
        batch_op.add_column(
            sa.Column("daily_reminder_time", sa.Time(), server_default="20:00:00", nullable=False)
        )
        batch_op.add_column(
            sa.Column("weekly_summary_enabled", sa.Boolean(), server_default="false", nullable=False)
        )
        batch_op.add_column(
            sa.Column("monthly_summary_enabled", sa.Boolean(), server_default="false", nullable=False)
        )
        batch_op.add_column(
            sa.Column("budget_alert_enabled", sa.Boolean(), server_default="true", nullable=False)
        )
        batch_op.add_column(
            sa.Column("timezone", sa.String(length=32), server_default="Asia/Jakarta", nullable=False)
        )
        batch_op.create_check_constraint(
            "ck_user_preferences_timezone",
            "timezone IN ('Asia/Jakarta', 'Asia/Makassar', 'Asia/Jayapura')",
        )


def downgrade() -> None:
    with op.batch_alter_table("user_preferences") as batch_op:
        batch_op.drop_constraint("ck_user_preferences_timezone", type_="check")
        batch_op.drop_column("timezone")
        batch_op.drop_column("budget_alert_enabled")
        batch_op.drop_column("monthly_summary_enabled")
        batch_op.drop_column("weekly_summary_enabled")
        batch_op.drop_column("daily_reminder_time")
        batch_op.drop_column("daily_reminder_enabled")
