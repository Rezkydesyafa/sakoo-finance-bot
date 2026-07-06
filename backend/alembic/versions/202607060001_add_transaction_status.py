"""add transaction status

Revision ID: 202607060001
Revises: 202607040001
Create Date: 2026-07-06 00:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "202607060001"
down_revision: str | None = "202607040001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="confirmed",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_transactions_status",
        "transactions",
        "status IN ('pending_confirmation', 'confirmed', 'cancelled')",
    )
    op.create_index(
        "ix_transactions_user_status_created",
        "transactions",
        ["user_id", "status", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_user_status_created", table_name="transactions")
    op.drop_constraint("ck_transactions_status", "transactions", type_="check")
    op.drop_column("transactions", "status")
