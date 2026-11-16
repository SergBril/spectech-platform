"""add_equipment_dynamic_attributes

Revision ID: 950950b062e8
Revises: 51c6d387f892
Create Date: 2026-09-23 21:12:49.510277

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "950950b062e8"  # pragma: allowlist secret
down_revision: str | None = "51c6d387f892"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # === 1. Создание таблицы equipment_attribute_definitions ===
    op.create_table(
        "equipment_attribute_definitions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("subcategory_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("slug", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("data_type", sa.String(length=20), nullable=False),
        sa.Column("unit", sa.String(length=20), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("allow_custom_values", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["subcategory_id"], ["categories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_equipment_attribute_definitions_subcategory_id"),
        "equipment_attribute_definitions",
        ["subcategory_id"],
        unique=False,
    )

    # === 2. Создание таблицы equipment_attribute_options ===
    op.create_table(
        "equipment_attribute_options",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("attribute_definition_id", sa.Integer(), nullable=False),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column("numeric_value", sa.Float(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_custom", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["attribute_definition_id"],
            ["equipment_attribute_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_equipment_attribute_options_attribute_definition_id"),
        "equipment_attribute_options",
        ["attribute_definition_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_equipment_attribute_options_company_id"),
        "equipment_attribute_options",
        ["company_id"],
        unique=False,
    )

    # === 3. Создание таблицы equipment_attribute_values ===
    op.create_table(
        "equipment_attribute_values",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vehicle_id", sa.Integer(), nullable=False),
        sa.Column("attribute_definition_id", sa.Integer(), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_number", sa.Float(), nullable=True),
        sa.Column("value_boolean", sa.Boolean(), nullable=True),
        sa.Column("attribute_option_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["attribute_definition_id"],
            ["equipment_attribute_definitions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["attribute_option_id"],
            ["equipment_attribute_options.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["vehicle_id"], ["vehicles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_equipment_attribute_values_attribute_definition_id"),
        "equipment_attribute_values",
        ["attribute_definition_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_equipment_attribute_values_vehicle_id"),
        "equipment_attribute_values",
        ["vehicle_id"],
        unique=False,
    )

    # === 4. Добавление колонок в categories ===
    op.add_column("categories", sa.Column("icon", sa.String(length=50), nullable=True))
    op.add_column("categories", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "categories",
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
    )

    # === 5. Добавление колонок в vehicles ===
    op.add_column(
        "vehicles",
        sa.Column(
            "make", sa.String(length=100), nullable=True, comment="Марка (CAT, Komatsu)"
        ),
    )
    op.add_column(
        "vehicles",
        sa.Column(
            "model",
            sa.String(length=100),
            nullable=True,
            comment="Модель (320D, PC200)",
        ),
    )
    op.add_column(
        "vehicles",
        sa.Column(
            "vin", sa.String(length=50), nullable=True, comment="VIN / серийный номер"
        ),
    )
    op.add_column(
        "vehicles",
        sa.Column(
            "custom_name",
            sa.String(length=255),
            nullable=True,
            comment="Пользовательское название",
        ),
    )

    # === 6. Создание индексов для vehicles ===
    op.create_index(
        op.f("ix_vehicles_category_id"), "vehicles", ["category_id"], unique=False
    )
    op.create_index(op.f("ix_vehicles_vin"), "vehicles", ["vin"], unique=False)


def downgrade() -> None:
    # Удаление индексов vehicles
    op.drop_index(op.f("ix_vehicles_vin"), table_name="vehicles")
    op.drop_index(op.f("ix_vehicles_category_id"), table_name="vehicles")

    # Удаление колонок vehicles
    op.drop_column("vehicles", "custom_name")
    op.drop_column("vehicles", "vin")
    op.drop_column("vehicles", "model")
    op.drop_column("vehicles", "make")

    # Удаление колонок categories
    op.drop_column("categories", "sort_order")
    op.drop_column("categories", "description")
    op.drop_column("categories", "icon")

    # Удаление таблиц equipment
    op.drop_index(
        op.f("ix_equipment_attribute_values_vehicle_id"),
        table_name="equipment_attribute_values",
    )
    op.drop_index(
        op.f("ix_equipment_attribute_values_attribute_definition_id"),
        table_name="equipment_attribute_values",
    )
    op.drop_table("equipment_attribute_values")

    op.drop_index(
        op.f("ix_equipment_attribute_options_company_id"),
        table_name="equipment_attribute_options",
    )
    op.drop_index(
        op.f("ix_equipment_attribute_options_attribute_definition_id"),
        table_name="equipment_attribute_options",
    )
    op.drop_table("equipment_attribute_options")

    op.drop_index(
        op.f("ix_equipment_attribute_definitions_subcategory_id"),
        table_name="equipment_attribute_definitions",
    )
    op.drop_table("equipment_attribute_definitions")
