"""shift meter readings: the missing distance column and cumulative end readings

Revision ID: c8d2e3f4a5b6
Revises: b7c1d2e3f4a5

odometer_distance вычислялся в mobile_shift_service и присваивался task, но колонки
не существовало ни в базе, ни в модели: SQLAlchemy клал атрибут на экземпляр, и
значение исчезало. Его читают diadoc.py (УПД) и shifts/mobile.py - документы
заказчику уходили без пробега смены.

Семантика колонок фиксируется явно:
  shift_tasks.odometer_start / moto_hours_start - НАКОПЛЕННЫЕ показания на начало
  shift_reports.odometer_end / moto_hours_end   - НАКОПЛЕННЫЕ показания на конец
  shift_reports.operator_odometer / operator_moto_hours - ВЫРАБОТКА за смену
  shift_tasks.odometer_distance - выработка по пробегу, читается документами
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c8d2e3f4a5b6"  # pragma: allowlist secret
down_revision: str | None = "b7c1d2e3f4a5"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "shift_tasks", sa.Column("odometer_distance", sa.Numeric(10, 1), nullable=True)
    )
    op.add_column(
        "shift_reports", sa.Column("odometer_end", sa.Integer(), nullable=True)
    )
    op.add_column(
        "shift_reports", sa.Column("moto_hours_end", sa.Numeric(10, 2), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("shift_reports", "moto_hours_end")
    op.drop_column("shift_reports", "odometer_end")
    op.drop_column("shift_tasks", "odometer_distance")
