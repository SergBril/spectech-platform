"""add telegram fields to users

Revision ID: 16373ca3d8d5
Revises: 58f0c2e7d2b3
Create Date: 2026-10-08 14:11:20.398028

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '16373ca3d8d5'
down_revision: Union[str, None] = '58f0c2e7d2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем telegram_id (BigInteger)
    op.add_column('users', sa.Column(
        'telegram_id', sa.BigInteger(), nullable=True,
        comment='Telegram user ID для привязки аккаунта'
    ))
    op.create_index('ix_users_telegram_id', 'users', ['telegram_id'], unique=True)
    
    # Добавляем telegram_link_code (одноразовый код привязки)
    op.add_column('users', sa.Column(
        'telegram_link_code', sa.String(32), nullable=True,
        comment='Одноразовый код для привязки Telegram'
    ))
    op.create_index('ix_users_telegram_link_code', 'users', ['telegram_link_code'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_telegram_link_code', table_name='users')
    op.drop_column('users', 'telegram_link_code')
    
    op.drop_index('ix_users_telegram_id', table_name='users')
    op.drop_column('users', 'telegram_id')