"""enhance categories table

Revision ID: 202607070001
Revises: 202607060001
Create Date: 2026-07-07

"""

from alembic import op
import sqlalchemy as sa


revision = "202607070001"
down_revision = "202607060001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop old constraints first
    op.drop_constraint("ck_categories_type", "categories", type_="check")
    op.drop_constraint("uq_categories_name_type", "categories", type_="unique")

    # Add new columns
    op.add_column(
        "categories",
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
    )
    op.add_column("categories", sa.Column("icon", sa.String(32), nullable=True))
    op.add_column("categories", sa.Column("color", sa.String(32), nullable=True))
    op.add_column("categories", sa.Column("keywords", sa.JSON(), nullable=True))
    op.add_column(
        "categories",
        sa.Column("is_default", sa.Boolean(), server_default="true", nullable=False),
    )
    op.add_column(
        "categories",
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
    )
    op.add_column(
        "categories",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Set all existing categories as default
    op.execute("UPDATE categories SET is_default = true, is_active = true")

    # Add updated type constraint (now includes 'both')
    op.create_check_constraint(
        "ck_categories_type",
        "categories",
        "type IN ('income', 'expense', 'both')",
    )

    # Add new unique constraint and index
    op.create_unique_constraint(
        "uq_categories_user_name_type",
        "categories",
        ["user_id", "name", "type"],
    )
    op.create_index("ix_categories_user_id", "categories", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_categories_user_id", table_name="categories")
    op.drop_constraint("uq_categories_user_name_type", "categories", type_="unique")
    op.drop_constraint("ck_categories_type", "categories", type_="check")

    op.drop_column("categories", "updated_at")
    op.drop_column("categories", "is_active")
    op.drop_column("categories", "is_default")
    op.drop_column("categories", "keywords")
    op.drop_column("categories", "color")
    op.drop_column("categories", "icon")
    op.drop_column("categories", "user_id")

    op.create_check_constraint(
        "ck_categories_type",
        "categories",
        "type IN ('income', 'expense')",
    )
    op.create_unique_constraint(
        "uq_categories_name_type",
        "categories",
        ["name", "type"],
    )
