"""add rental_id to acts and make request_id nullable

Revision ID: c88261b247a6
Revises: a4d1a15f105e
Create Date: 2026-10-07 ...

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c88261b247a6'
down_revision: Union[str, None] = 'a4d1a15f105e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Добавляем rental_id в acts
    op.add_column('acts', sa.Column('rental_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'acts_rental_id_fkey',
        'acts', 'rentals',
        ['rental_id'], ['id'],
        ondelete='SET NULL'
    )
    
    # 2. Делаем request_id nullable
    op.alter_column('acts', 'request_id',
               existing_type=sa.Integer(),
               nullable=True)


def downgrade() -> None:
    op.alter_column('acts', 'request_id',
               existing_type=sa.Integer(),
               nullable=False)
    op.drop_constraint('acts_rental_id_fkey', 'acts', type_='foreignkey')
    op.drop_column('acts', 'rental_id')