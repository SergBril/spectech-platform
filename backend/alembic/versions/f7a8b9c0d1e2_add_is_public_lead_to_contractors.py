"""add is_public_lead to contractors

Revision ID: f7a8b9c0d1e2
Revises: e48fbe2e243c
Create Date: 2026-10-29
"""

import sqlalchemy as sa

from alembic import op

revision = "f7a8b9c0d1e2"
down_revision = "e48fbe2e243c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "contractors",
        sa.Column(
            "is_public_lead", sa.Boolean(), nullable=False, server_default="false"
        ),
    )


def downgrade() -> None:
    op.drop_column("contractors", "is_public_lead")
