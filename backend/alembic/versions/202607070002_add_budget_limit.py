"""add budget_limit to categories

Revision ID: 202607070002
Revises: 202607070001
Create Date: 2026-07-06 16:47:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '202607070002'
down_revision: Union[str, None] = '202607070001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('categories', sa.Column('budget_limit', sa.Numeric(precision=14, scale=2), nullable=True))


def downgrade() -> None:
    op.drop_column('categories', 'budget_limit')
