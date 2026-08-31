from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.auth import User
from app.models.rbac import Role, Permission, RolePermission, UserRole


# Системные роли, создаются при инициализации
SYSTEM_ROLES = [
    {"code": "admin", "name": "Администратор", "description": "Полный доступ ко всему"},
    {"code": "dispatcher", "name": "Диспетчер", "description": "Управление заявками и техникой"},
    {"code": "operator", "name": "Оператор", "description": "Работа со сменными заданиями"},
    {"code": "client", "name": "Клиент", "description": "Просмотр своих заявок и документов"},
    {"code": "owner", "name": "Собственник", "description": "Просмотр доходов и техники"},
    {"code": "mechanic", "name": "Механик", "description": "Осмотр и ремонт техники"},
]

# Базовые права
SYSTEM_PERMISSIONS = [
    # Техника
    ("vehicles", "view"),
    ("vehicles", "create"),
    ("vehicles", "update"),
    ("vehicles", "delete"),
    # Заявки
    ("requests", "view"),
    ("requests", "create"),
    ("requests", "assign"),
    ("requests", "update"),
    ("requests", "cancel"),
    # Смены
    ("shifts", "view"),
    ("shifts", "create"),
    ("shifts", "approve"),
    # Контрагенты
    ("contractors", "view"),
    ("contractors", "create"),
    ("contractors", "update"),
    # RBAC
    ("rbac", "manage"),
    # Справочники
    ("catalogs", "manage"),
        # Финансы
    ("invoices", "view"),
    ("invoices", "create"),
    ("invoices", "update"),
    ("invoices", "send"),
    ("acts", "view"),
    ("acts", "create"),
    ("acts", "sign"),
    ("payouts", "view"),
    ("payouts", "create"),
    ("payouts", "pay"),
    ("payments", "view"),
    ("finance", "dashboard"),
]


def init_system_data(db: Session) -> None:
    """Создаёт системные роли и права если их нет."""
    # Создаём права
    for entity, action in SYSTEM_PERMISSIONS:
        existing = db.scalar(
            select(Permission).where(
                Permission.entity == entity,
                Permission.action == action,
            )
        )
        if not existing:
            db.add(Permission(entity=entity, action=action))
    
    # Создаём роли
    for role_data in SYSTEM_ROLES:
        existing = db.scalar(
            select(Role).where(Role.code == role_data["code"])
        )
        if not existing:
            role = Role(
                code=role_data["code"],
                name=role_data["name"],
                description=role_data["description"],
                is_system=True,
            )
            db.add(role)
    
    db.flush()
    
    # Маппинг прав по ролям
    role_permissions_map = {
        "admin": [
            # Админ имеет ВСЕ права
            ("vehicles", "view"), ("vehicles", "create"), ("vehicles", "update"), ("vehicles", "delete"),
            ("requests", "view"), ("requests", "create"), ("requests", "assign"), ("requests", "update"), ("requests", "cancel"),
            ("shifts", "view"), ("shifts", "create"), ("shifts", "approve"),
            ("contractors", "view"), ("contractors", "create"), ("contractors", "update"),
            ("rbac", "manage"),
            ("catalogs", "manage"),("invoices", "view"), ("invoices", "create"), ("invoices", "update"), ("invoices", "send"),
("acts", "view"), ("acts", "create"), ("acts", "sign"),
("payouts", "view"), ("payouts", "create"), ("payouts", "pay"),
("payments", "view"), ("finance", "dashboard"),
        ],
        "dispatcher": [
            ("vehicles", "view"), ("vehicles", "create"), ("vehicles", "update"),
            ("requests", "view"), ("requests", "create"), ("requests", "assign"), ("requests", "update"),
            ("shifts", "view"), ("shifts", "create"),
            ("contractors", "view"),
            ("catalogs", "manage"),("invoices", "view"), ("invoices", "create"),
("acts", "view"), ("acts", "create"),
("payouts", "view"),
("payments", "view"), ("finance", "dashboard"),
        ],
        "operator": [
            ("vehicles", "view"),
            ("requests", "view"),
            ("shifts", "view"), ("shifts", "create"),
        ],
        "client": [
            ("requests", "view"),
            ("shifts", "view"),("invoices", "view"),
("acts", "view"),
("payments", "view"),
        ],
        "owner": [
            ("vehicles", "view"),
            ("requests", "view"),
            ("shifts", "view"),("payouts", "view"),
("payments", "view"), ("finance", "dashboard"),
        ],
        "mechanic": [
            ("vehicles", "view"), ("vehicles", "update"),
        ],
    }
    
    # Назначаем права ролям
    for role_code, perms_list in role_permissions_map.items():
        role = db.scalar(select(Role).where(Role.code == role_code))
        if not role:
            continue
        
        for entity, action in perms_list:
            perm = db.scalar(
                select(Permission).where(
                    Permission.entity == entity,
                    Permission.action == action,
                )
            )
            if not perm:
                continue
            
            existing = db.scalar(
                select(RolePermission).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id == perm.id,
                )
            )
            if not existing:
                db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    
    db.commit()


def get_user_permissions(db: Session, user: User) -> set[str]:
    """Возвращает множество прав пользователя в формате 'entity:action'."""
    if user.is_superuser:
        # Суперпользователь имеет все права
        all_perms = db.scalars(select(Permission)).all()
        return {f"{p.entity}:{p.action}" for p in all_perms}
    
    # Получаем все роли пользователя
    user_roles = db.scalars(
        select(UserRole).where(
            UserRole.user_id == user.id,
            UserRole.is_active == True,
        )
    ).all()
    
    permissions = set()
    for ur in user_roles:
        role_perms = db.scalars(
            select(RolePermission).where(RolePermission.role_id == ur.role_id)
        ).all()
        for rp in role_perms:
            perm = db.get(Permission, rp.permission_id)
            if perm:
                permissions.add(f"{perm.entity}:{perm.action}")
    
    return permissions


def check_permission(
    db: Session,
    user: User,
    entity: str,
    action: str,
) -> bool:
    """Проверяет есть ли у пользователя право entity:action."""
    if user.is_superuser:
        return True
    
    perms = get_user_permissions(db, user)
    return f"{entity}:{action}" in perms


def require_permission(db: Session, user: User, entity: str, action: str) -> None:
    """Проверяет право и выбрасывает 403 если его нет."""
    if not check_permission(db, user, entity, action):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied: {entity}:{action}",
        )