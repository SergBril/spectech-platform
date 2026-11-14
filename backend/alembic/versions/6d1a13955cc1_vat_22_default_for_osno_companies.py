"""vat 22 default for osno companies

Revision ID: 6d1a13955cc1
Revises: 56df21b4b7f0
Create Date: 2026-11-13 17:56:26.907442

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6d1a13955cc1"  # pragma: allowlist secret
down_revision: str | None = "56df21b4b7f0"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """ОСНО: ставка по умолчанию 22% с 2026 года.

    Меняем server_default и обновляем компании, у которых стоит прежняя
    стандартная ставка 20% на ОСНО. Компании на УСН/Патент/НПД и те, где
    выбрана иная ставка, не затрагиваются.

    Документы (invoices/acts/payouts) НЕ пересчитываются: их vat_rate и
    vat_amount зафиксированы в первичке.
    """
    op.alter_column(
        "companies",
        "default_vat_rate",
        existing_type=sa.Numeric(precision=5, scale=2),
        server_default="22.00",
        existing_nullable=False,
    )
    op.execute(
        "UPDATE companies SET default_vat_rate = 22.00 "
        "WHERE default_vat_rate = 20.00 AND default_tax_system = 'osno'"
    )


def downgrade() -> None:
    """Возвращаем server_default. Данные намеренно не откатываем.

    После апгрейда пользователь может выставить 22% вручную, и откат не
    отличит такое значение от проставленного нами - обратный UPDATE мог бы
    сбросить осознанный выбор. Поэтому data-часть необратима.
    """
    op.alter_column(
        "companies",
        "default_vat_rate",
        existing_type=sa.Numeric(precision=5, scale=2),
        server_default="20.00",
        existing_nullable=False,
    )
