"""add income daily categories

Revision ID: 202606290001
Revises: 202606270003
Create Date: 2026-06-29 00:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "202606290001"
down_revision: str | None = "202606270003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CATEGORIES = [
    {"name": "Uang Saku", "type": "income"},
    {"name": "Lainnya", "type": "income"},
]


def upgrade() -> None:
    connection = op.get_bind()
    categories_table = sa.table(
        "categories",
        sa.column("name", sa.String),
        sa.column("type", sa.String),
    )
    for category in CATEGORIES:
        exists = connection.execute(
            sa.select(sa.literal(1)).select_from(categories_table).where(
                categories_table.c.name == category["name"],
                categories_table.c.type == category["type"],
            )
        ).first()
        if not exists:
            connection.execute(categories_table.insert().values(**category))


def downgrade() -> None:
    categories_table = sa.table(
        "categories",
        sa.column("name", sa.String),
        sa.column("type", sa.String),
    )
    for category in CATEGORIES:
        op.execute(
            categories_table.delete().where(
                categories_table.c.name == category["name"],
                categories_table.c.type == category["type"],
            )
        )
