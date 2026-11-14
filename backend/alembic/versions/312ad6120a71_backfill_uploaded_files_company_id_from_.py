"""backfill uploaded_files company_id from documents

Revision ID: 312ad6120a71
Revises: 16bd149120da
Create Date: 2026-11-14 11:27:43.619867

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "312ad6120a71"  # pragma: allowlist secret
down_revision: str | None = "16bd149120da"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Восстанавливаем компанию у файлов, созданных до tenant-привязки.

    48 файлов имели company_id IS NULL. После введения fail-closed проверки
    владения они стали недоступны всем, включая владельцев. Компания
    выводится из связанного документа: 31 invoice_pdf через invoice_id,
    16 act_pdf через act_id.

    Один act_pdf не имеет ни invoice_id, ни act_id - атрибутировать его не
    из чего, он остаётся с NULL и закрыт. Это осознанный fail-closed.
    """
    op.execute(
        "UPDATE uploaded_files f SET company_id = i.company_id "
        "FROM invoices i "
        "WHERE f.invoice_id = i.id AND f.company_id IS NULL "
        "AND i.company_id IS NOT NULL"
    )
    op.execute(
        "UPDATE uploaded_files f SET company_id = a.company_id "
        "FROM acts a "
        "WHERE f.act_id = a.id AND f.company_id IS NULL "
        "AND a.company_id IS NOT NULL"
    )


def downgrade() -> None:
    """Данные намеренно не откатываем.

    Обнуление company_id вернуло бы файлы в недоступное состояние, а
    отличить восстановленные нами строки от изначально заполненных
    невозможно. Структурных изменений здесь нет, откатывать нечего.
    """
