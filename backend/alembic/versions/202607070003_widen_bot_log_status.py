"""widen bot log status

Revision ID: 202607070003
Revises: 202607070002
Create Date: 2026-07-07 10:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202607070003"
down_revision: Union[str, None] = "202607070002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        return
    op.alter_column("bot_logs", "status", type_=sa.String(length=64))


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        return
    op.alter_column("bot_logs", "status", type_=sa.String(length=32))
