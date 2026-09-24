"""Pydantic схемы для каталога техники."""

from pydantic import BaseModel, Field


class AttributeOptionRead(BaseModel):
    """Вариант значения атрибута."""

    id: int
    value: str
    numeric_value: float | None = None
    sort_order: int
    is_custom: bool = False

    model_config = {"from_attributes": True}


class AttributeDefinitionRead(BaseModel):
    """Определение атрибута."""

    id: int
    name: str
    slug: str
    description: str | None = None
    data_type: str  # select / number / text / boolean
    unit: str | None = None
    is_required: bool = False
    allow_custom_values: bool = True
    sort_order: int
    options: list[AttributeOptionRead] = []

    model_config = {"from_attributes": True}


class SubcategoryRead(BaseModel):
    """Подкатегория техники."""

    id: int
    code: str
    name: str
    icon: str | None = None
    sort_order: int
    attribute_count: int = 0

    model_config = {"from_attributes": True}


class CategoryTreeRead(BaseModel):
    """Категория с подкатегориями (дерево)."""

    id: int
    code: str
    name: str
    icon: str | None = None
    description: str | None = None
    sort_order: int
    subcategories: list[SubcategoryRead] = []

    model_config = {"from_attributes": True}


class AttributeOptionCreate(BaseModel):
    """Добавление пользовательского варианта."""

    value: str = Field(..., min_length=1, max_length=255)
    numeric_value: float | None = None
