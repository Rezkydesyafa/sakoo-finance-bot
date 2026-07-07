"""add receipt caption text

Revision ID: 202606290002
Revises: 202606290001
Create Date: 2026-06-29 00:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "202606290002"
down_revision: str | None = "202606290001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("receipts")}
    if "caption_text" not in columns:
        op.add_column(
            "receipts",
            sa.Column("caption_text", sa.Text(), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("receipts", "caption_text")
