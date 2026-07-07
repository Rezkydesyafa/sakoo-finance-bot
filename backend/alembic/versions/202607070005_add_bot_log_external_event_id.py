"""add bot log external event id

Revision ID: 202607070005
Revises: 202607070004
Create Date: 2026-07-07 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "202607070005"
down_revision: Union[str, None] = "202607070004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    if "external_event_id" not in _columns("bot_logs"):
        op.add_column("bot_logs", sa.Column("external_event_id", sa.String(length=160), nullable=True))
    if "uq_bot_logs_platform_external_event" not in _indexes("bot_logs"):
        op.create_index(
            "uq_bot_logs_platform_external_event",
            "bot_logs",
            ["platform", "external_event_id"],
            unique=True,
        )


def downgrade() -> None:
    if "uq_bot_logs_platform_external_event" in _indexes("bot_logs"):
        op.drop_index("uq_bot_logs_platform_external_event", table_name="bot_logs")
    if "external_event_id" in _columns("bot_logs"):
        op.drop_column("bot_logs", "external_event_id")
