"""add password reset fields

Revision ID: b7c8d9e0f1a2
Revises: a33b982eb9ef
Create Date: 2026-10-20 15:30:00.000000

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "b7c8d9e0f1a2"
down_revision = "a33b982eb9ef"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "reset_token_hash",
            sa.String(length=255),
            nullable=True,
            comment="Hashed token для сброса пароля",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "reset_token_expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Время истечения reset токена",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "reset_token_expires_at")
    op.drop_column("users", "reset_token_hash")
