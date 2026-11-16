"""add per-company edo settings

Revision ID: e7abeaae0846
Revises: 312ad6120a71
Create Date: 2026-11-15 10:55:21.065154

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7abeaae0846"  # pragma: allowlist secret
down_revision: str | None = "312ad6120a71"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Настройки ЭДО компании.

    Роуты GET/PUT /edo-settings существовали, но ни одной из этих колонок
    не было: PUT собирал updates и отбрасывал всё через `if hasattr(company, key)`,
    возвращая {"message": "EDO settings updated"} при нулевой записи.
    Проверено замером: PUT diadoc_api_key -> 200, GET после -> пустая строка.

    diadoc_api_key и sbis_token - Text, потому что хранятся зашифрованными
    (Fernet), и шифртекст длиннее исходного значения.
    """
    op.add_column(
        "companies",
        sa.Column(
            "edo_operator", sa.String(50), nullable=True, server_default="diadoc"
        ),
    )
    op.add_column("companies", sa.Column("diadoc_api_key", sa.Text(), nullable=True))
    op.add_column(
        "companies", sa.Column("diadoc_box_id", sa.String(255), nullable=True)
    )
    op.add_column(
        "companies",
        sa.Column(
            "diadoc_use_sandbox", sa.Boolean(), nullable=True, server_default=sa.true()
        ),
    )
    op.add_column("companies", sa.Column("sbis_token", sa.Text(), nullable=True))
    op.add_column(
        "companies", sa.Column("sbis_client_id", sa.String(255), nullable=True)
    )
    op.add_column(
        "companies",
        sa.Column(
            "auto_send_on_sign", sa.Boolean(), nullable=True, server_default=sa.false()
        ),
    )
    op.add_column(
        "companies",
        sa.Column(
            "default_format", sa.String(50), nullable=True, server_default="upd_5_03"
        ),
    )


def downgrade() -> None:
    for col in (
        "default_format",
        "auto_send_on_sign",
        "sbis_client_id",
        "sbis_token",
        "diadoc_use_sandbox",
        "diadoc_box_id",
        "diadoc_api_key",
        "edo_operator",
    ):
        op.drop_column("companies", col)
