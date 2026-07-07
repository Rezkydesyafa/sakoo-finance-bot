"""ensure category budgets table

Revision ID: 202607070004
Revises: 202607070003
Create Date: 2026-07-07 20:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202607070004"
down_revision: Union[str, None] = "202607070003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    return any(index["name"] == index_name for index in sa.inspect(bind).get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("category_budgets"):
        op.create_table(
            "category_budgets",
            sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True),
            sa.Column("user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
            sa.Column("category_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
            sa.Column("monthly_limit", sa.Numeric(precision=14, scale=2), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("user_id", "category_id", name="uq_category_budgets_user_category"),
        )

    if not _has_index("category_budgets", "ix_category_budgets_user_id"):
        op.create_index("ix_category_budgets_user_id", "category_budgets", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("category_budgets"):
        if _has_index("category_budgets", "ix_category_budgets_user_id"):
            op.drop_index("ix_category_budgets_user_id", table_name="category_budgets")
        op.drop_table("category_budgets")
