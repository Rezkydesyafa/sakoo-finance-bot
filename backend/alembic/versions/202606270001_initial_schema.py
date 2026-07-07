"""initial schema

Revision ID: 202606270001
Revises:
Create Date: 2026-06-27 00:00:00
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "202606270001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEFAULT_CATEGORIES = [
    {"name": "Makanan", "type": "expense"},
    {"name": "Transportasi", "type": "expense"},
    {"name": "Tagihan", "type": "expense"},
    {"name": "Belanja", "type": "expense"},
    {"name": "Hiburan", "type": "expense"},
    {"name": "Kesehatan", "type": "expense"},
    {"name": "Pendidikan", "type": "expense"},
    {"name": "Gaji", "type": "income"},
    {"name": "Uang Saku", "type": "income"},
    {"name": "Tabungan", "type": "income"},
    {"name": "Lainnya", "type": "expense"},
    {"name": "Lainnya", "type": "income"},
]

BIGINT_PK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", BIGINT_PK, primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("phone_number", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_phone_number", "users", ["phone_number"], unique=True)

    op.create_table(
        "categories",
        sa.Column("id", BIGINT_PK, primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("type IN ('income', 'expense')", name="ck_categories_type"),
        sa.UniqueConstraint("name", "type", name="uq_categories_name_type"),
    )

    categories_table = sa.table(
        "categories",
        sa.column("name", sa.String),
        sa.column("type", sa.String),
    )
    op.bulk_insert(categories_table, DEFAULT_CATEGORIES)

    op.create_table(
        "user_platform_accounts",
        sa.Column("id", BIGINT_PK, primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("platform_user_id", sa.String(length=128), nullable=True),
        sa.Column("phone_number", sa.String(length=32), nullable=True),
        sa.Column("chat_id", sa.String(length=128), nullable=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.CheckConstraint(
            "platform IN ('whatsapp', 'telegram')",
            name="ck_user_platform_accounts_platform",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "platform", name="uq_user_platform_accounts_user_platform"),
        sa.UniqueConstraint(
            "platform",
            "platform_user_id",
            name="uq_user_platform_accounts_platform_user_id",
        ),
    )

    op.create_table(
        "account_linking_codes",
        sa.Column("id", BIGINT_PK, primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_account_linking_codes_code", "account_linking_codes", ["code"], unique=True)
    op.create_index("ix_account_linking_codes_user_id", "account_linking_codes", ["user_id"])

    op.create_table(
        "transactions",
        sa.Column("id", BIGINT_PK, primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("type IN ('income', 'expense')", name="ck_transactions_type"),
        sa.CheckConstraint(
            "source IN ('whatsapp_text', 'telegram_text', 'dashboard_manual', "
            "'receipt_ocr', 'voice_note')",
            name="ck_transactions_source",
        ),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_transactions_user_category", "transactions", ["user_id", "category_id"])
    op.create_index("ix_transactions_user_date", "transactions", ["user_id", "transaction_date"])

    op.create_table(
        "media_files",
        sa.Column("id", BIGINT_PK, primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("file_type", sa.String(length=32), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("stored_path", sa.String(length=512), nullable=False),
        sa.Column("mime_type", sa.String(length=128), nullable=True),
        sa.Column("size", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_media_files_user_id", "media_files", ["user_id"])

    op.create_table(
        "receipts",
        sa.Column("id", BIGINT_PK, primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("media_file_id", sa.BigInteger(), nullable=False),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("merchant_name", sa.String(length=160), nullable=True),
        sa.Column("receipt_date", sa.Date(), nullable=True),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("transaction_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["media_file_id"], ["media_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_receipts_user_id", "receipts", ["user_id"])

    op.create_table(
        "voice_notes",
        sa.Column("id", BIGINT_PK, primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("media_file_id", sa.BigInteger(), nullable=False),
        sa.Column("transcript_text", sa.Text(), nullable=True),
        sa.Column("stt_provider", sa.String(length=80), nullable=True),
        sa.Column("transaction_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["media_file_id"], ["media_files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transaction_id"], ["transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_voice_notes_user_id", "voice_notes", ["user_id"])

    op.create_table(
        "reports",
        sa.Column("id", BIGINT_PK, primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("report_type", sa.String(length=32), nullable=False),
        sa.Column("file_id", sa.BigInteger(), nullable=True),
        sa.Column("generated_from", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["file_id"], ["media_files.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_reports_user_period", "reports", ["user_id", "period_start", "period_end"])

    op.create_table(
        "jobs",
        sa.Column("id", BIGINT_PK, primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("job_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("result_id", sa.BigInteger(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_jobs_user_status", "jobs", ["user_id", "status"])

    op.create_table(
        "bot_logs",
        sa.Column("id", BIGINT_PK, primary_key=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("message_type", sa.String(length=40), nullable=False),
        sa.Column("raw_message", sa.Text(), nullable=True),
        sa.Column("parsed_result", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_bot_logs_user_created_at", "bot_logs", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_bot_logs_user_created_at", table_name="bot_logs")
    op.drop_table("bot_logs")

    op.drop_index("ix_jobs_user_status", table_name="jobs")
    op.drop_table("jobs")

    op.drop_index("ix_reports_user_period", table_name="reports")
    op.drop_table("reports")

    op.drop_index("ix_voice_notes_user_id", table_name="voice_notes")
    op.drop_table("voice_notes")

    op.drop_index("ix_receipts_user_id", table_name="receipts")
    op.drop_table("receipts")

    op.drop_index("ix_media_files_user_id", table_name="media_files")
    op.drop_table("media_files")

    op.drop_index("ix_transactions_user_date", table_name="transactions")
    op.drop_index("ix_transactions_user_category", table_name="transactions")
    op.drop_table("transactions")

    op.drop_index("ix_account_linking_codes_user_id", table_name="account_linking_codes")
    op.drop_index("ix_account_linking_codes_code", table_name="account_linking_codes")
    op.drop_table("account_linking_codes")

    op.drop_table("user_platform_accounts")
    op.drop_table("categories")

    op.drop_index("ix_users_phone_number", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
