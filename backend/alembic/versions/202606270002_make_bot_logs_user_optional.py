"""make bot log user optional

Revision ID: 202606270002
Revises: 202606270001
Create Date: 2026-06-27 00:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "202606270002"
down_revision: str | None = "202606270001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        return
    op.drop_constraint("bot_logs_user_id_fkey", "bot_logs", type_="foreignkey")
    op.alter_column(
        "bot_logs",
        "user_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.create_foreign_key(
        "bot_logs_user_id_fkey",
        "bot_logs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        return
    op.drop_constraint("bot_logs_user_id_fkey", "bot_logs", type_="foreignkey")
    op.alter_column(
        "bot_logs",
        "user_id",
        existing_type=sa.BigInteger(),
        nullable=False,
    )
    op.create_foreign_key(
        "bot_logs_user_id_fkey",
        "bot_logs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
