"""add email templates and logs

Revision ID: 51c6d387f892
Revises: a7bb5c034567
Create Date: 2026-09-23 13:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision: str = "51c6d387f892"  # pragma: allowlist secret
down_revision: Union[str, None] = "a7bb5c034567"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # === Таблица email_templates ===
    op.create_table(
        "email_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("template_type", sa.String(50), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("html_body", sa.Text(), nullable=False),
        sa.Column("text_body", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "is_default", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_email_templates_company", "email_templates", ["company_id"])
    op.create_index("idx_email_templates_type", "email_templates", ["template_type"])

    # === Таблица email_logs ===
    op.create_table(
        "email_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False
        ),
        sa.Column(
            "template_id",
            sa.Integer(),
            sa.ForeignKey("email_templates.id"),
            nullable=True,
        ),
        sa.Column("to_email", sa.String(255), nullable=False),
        sa.Column("to_name", sa.String(255), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("html_body", sa.Text(), nullable=True),
        sa.Column("text_body", sa.Text(), nullable=True),
        sa.Column("attachments", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invoice_id", sa.Integer(), nullable=True),
        sa.Column("act_id", sa.Integer(), nullable=True),
        sa.Column("maintenance_order_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("idx_email_logs_company", "email_logs", ["company_id"])
    op.create_index("idx_email_logs_status", "email_logs", ["status"])
    op.create_index("idx_email_logs_created", "email_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_email_logs_created", table_name="email_logs")
    op.drop_index("idx_email_logs_status", table_name="email_logs")
    op.drop_index("idx_email_logs_company", table_name="email_logs")
    op.drop_table("email_logs")

    op.drop_index("idx_email_templates_type", table_name="email_templates")
    op.drop_index("idx_email_templates_company", table_name="email_templates")
    op.drop_table("email_templates")
