"""add transaction filter indexes

Revision ID: 202606270003
Revises: 202606270002
Create Date: 2026-06-27 00:00:00
"""
from collections.abc import Sequence

from alembic import op


revision: str = "202606270003"
down_revision: str | None = "202606270002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_transactions_user_type_date",
        "transactions",
        ["user_id", "type", "transaction_date"],
    )
    op.create_index(
        "ix_transactions_user_category_date",
        "transactions",
        ["user_id", "category_id", "transaction_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_user_category_date", table_name="transactions")
    op.drop_index("ix_transactions_user_type_date", table_name="transactions")
