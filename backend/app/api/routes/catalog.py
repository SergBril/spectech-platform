"""🚜 API endpoints для каталога техники."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.catalog import (
    Category,
    EquipmentAttributeDefinition,
    EquipmentAttributeOption,
)
from app.schemas.catalog import (
    AttributeDefinitionRead,
    AttributeOptionCreate,
    AttributeOptionRead,
    CategoryTreeRead,
    SubcategoryRead,
)

router = APIRouter(prefix="/catalog", tags=["🚜 Equipment Catalog"])


@router.get(
    "/tree",
    response_model=list[CategoryTreeRead],
    summary="Дерево категорий с подкатегориями",
)
def get_catalog_tree(db: Session = Depends(get_db)):
    """
    Получить дерево категорий верхнего уровня с вложенными подкатегориями.

    Используется для построения каскадного выбора на фронтенде.
    """
    # Получаем все активные категории верхнего уровня
    categories = (
        db.query(Category)
        .filter(Category.level == 1, Category.is_active == True)
        .order_by(Category.sort_order)
        .all()
    )

    result = []
    for cat in categories:
        # Получаем подкатегории для каждой категории
        subcategories = (
            db.query(Category)
            .filter(
                Category.parent_id == cat.id,
                Category.level == 2,
                Category.is_active == True,
            )
            .order_by(Category.sort_order)
            .all()
        )

        # Подсчёт атрибутов для каждой подкатегории
        sub_list = []
        for sub in subcategories:
            attr_count = (
                db.query(EquipmentAttributeDefinition)
                .filter(
                    EquipmentAttributeDefinition.subcategory_id == sub.id,
                    EquipmentAttributeDefinition.is_active == True,
                )
                .count()
            )
            sub_list.append(
                SubcategoryRead(
                    id=sub.id,
                    code=sub.code,
                    name=sub.name,
                    icon=sub.icon,
                    sort_order=sub.sort_order,
                    attribute_count=attr_count,
                )
            )

        result.append(
            CategoryTreeRead(
                id=cat.id,
                code=cat.code,
                name=cat.name,
                icon=cat.icon,
                description=cat.description,
                sort_order=cat.sort_order,
                subcategories=sub_list,
            )
        )

    return result


@router.get(
    "/subcategories/{subcategory_id}/attributes",
    response_model=list[AttributeDefinitionRead],
    summary="Атрибуты подкатегории",
)
def get_subcategory_attributes(
    subcategory_id: int,
    db: Session = Depends(get_db),
):
    """
    Получить атрибуты подкатегории с вариантами значений.

    Используется для динамической генерации формы атрибутов на фронтенде.
    """
    # Проверяем, что подкатегория существует
    subcategory = db.get(Category, subcategory_id)
    if not subcategory or subcategory.level != 2:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Подкатегория не найдена",
        )

    # Получаем атрибуты
    attributes = (
        db.query(EquipmentAttributeDefinition)
        .filter(
            EquipmentAttributeDefinition.subcategory_id == subcategory_id,
            EquipmentAttributeDefinition.is_active == True,
        )
        .order_by(EquipmentAttributeDefinition.sort_order)
        .all()
    )

    result = []
    for attr in attributes:
        # Получаем варианты значений для атрибутов типа select
        options = []
        if attr.data_type == "select":
            options = (
                db.query(EquipmentAttributeOption)
                .filter(
                    EquipmentAttributeOption.attribute_definition_id == attr.id,
                    EquipmentAttributeOption.is_active == True,
                )
                .order_by(EquipmentAttributeOption.sort_order)
                .all()
            )

        result.append(
            AttributeDefinitionRead(
                id=attr.id,
                name=attr.name,
                slug=attr.slug,
                description=attr.description,
                data_type=attr.data_type,
                unit=attr.unit,
                is_required=attr.is_required,
                allow_custom_values=attr.allow_custom_values,
                sort_order=attr.sort_order,
                options=[
                    AttributeOptionRead(
                        id=opt.id,
                        value=opt.value,
                        numeric_value=opt.numeric_value,
                        sort_order=opt.sort_order,
                        is_custom=opt.is_custom,
                    )
                    for opt in options
                ],
            )
        )

    return result


@router.post(
    "/attributes/{attribute_id}/options",
    response_model=AttributeOptionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить пользовательский вариант значения",
)
def add_custom_option(
    attribute_id: int,
    payload: AttributeOptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Добавить пользовательский вариант значения для атрибута типа select.

    Используется, когда пользователю нужно значение, которого нет в предопределённых.
    """
    # Проверяем, что атрибут существует
    attribute = db.get(EquipmentAttributeDefinition, attribute_id)
    if not attribute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Атрибут не найден",
        )

    if not attribute.allow_custom_values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользовательские значения не разрешены для этого атрибута",
        )

    # Проверяем дубликаты
    existing = (
        db.query(EquipmentAttributeOption)
        .filter(
            EquipmentAttributeOption.attribute_definition_id == attribute_id,
            EquipmentAttributeOption.value == payload.value,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Такой вариант уже существует",
        )

    # Определяем следующий sort_order
    max_order = (
        db.query(EquipmentAttributeOption)
        .filter(EquipmentAttributeOption.attribute_definition_id == attribute_id)
        .count()
    )

    # Создаём вариант
    option = EquipmentAttributeOption(
        attribute_definition_id=attribute_id,
        value=payload.value,
        numeric_value=payload.numeric_value,
        sort_order=max_order,
        is_custom=True,
        created_by_user_id=current_user.id,
        company_id=current_user.company_id,
    )
    db.add(option)
    db.commit()
    db.refresh(option)

    return AttributeOptionRead(
        id=option.id,
        value=option.value,
        numeric_value=option.numeric_value,
        sort_order=option.sort_order,
        is_custom=option.is_custom,
    )
