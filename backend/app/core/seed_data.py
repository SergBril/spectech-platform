"""Seed script для создания начальных данных (роли, permissions, пользователи)."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User, UserStatus
from app.models.rbac import Permission, Role, RolePermission, UserRole
from app.services.auth_service import hash_password


def seed_permissions(db: Session) -> dict[str, Permission]:
    """Создать базовые permissions для всех сущностей."""
    permissions_data = [
        # Vehicles
        ("vehicles", "create"),
        ("vehicles", "read"),
        ("vehicles", "update"),
        ("vehicles", "delete"),
        # Invoices
        ("invoices", "create"),
        ("invoices", "read"),
        ("invoices", "update"),
        ("invoices", "delete"),
        # Acts
        ("acts", "create"),
        ("acts", "read"),
        ("acts", "update"),
        ("acts", "delete"),
        # Users
        ("users", "create"),
        ("users", "read"),
        ("users", "update"),
        ("users", "delete"),
        # System
        ("system", "admin_access"),
        ("system", "view_metrics"),
    ]

    permissions = {}
    for entity, action in permissions_data:
        perm = (
            db.query(Permission)
            .filter(Permission.entity == entity, Permission.action == action)
            .first()
        )

        if not perm:
            perm = Permission(entity=entity, action=action)
            db.add(perm)
            db.flush()

        permissions[f"{entity}:{action}"] = perm

    return permissions


def seed_roles(db: Session, permissions: dict[str, Permission]) -> dict[str, Role]:
    """Создать базовые роли и назначить им permissions."""
    roles_data = {
        "admin": {
            "name": "Administrator",
            "description": "Full system access",
            "is_system": True,
            "permissions": list(permissions.keys()),  # Все permissions
        },
        "manager": {
            "name": "Manager",
            "description": "Manage vehicles, invoices, acts",
            "is_system": True,
            "permissions": [
                "vehicles:create",
                "vehicles:read",
                "vehicles:update",
                "vehicles:delete",
                "invoices:create",
                "invoices:read",
                "invoices:update",
                "invoices:delete",
                "acts:create",
                "acts:read",
                "acts:update",
                "acts:delete",
                "users:read",
                "system:view_metrics",
            ],
        },
        "operator": {
            "name": "Operator",
            "description": "View and create basic entities",
            "is_system": True,
            "permissions": [
                "vehicles:read",
                "invoices:read",
                "invoices:create",
                "acts:read",
                "acts:create",
            ],
        },
        "client": {
            "name": "Client",
            "description": "View own invoices and acts",
            "is_system": True,
            "permissions": [
                "vehicles:read",
                "invoices:read",
                "acts:read",
            ],
        },
        "owner": {
            "name": "Vehicle Owner",
            "description": "Manage own vehicles",
            "is_system": True,
            "permissions": [
                "vehicles:read",
                "vehicles:update",
            ],
        },
    }

    roles = {}
    for role_code, role_data in roles_data.items():
        role = db.query(Role).filter(Role.code == role_code).first()

        if not role:
            role = Role(
                code=role_code,
                name=role_data["name"],
                description=role_data["description"],
                is_system=role_data["is_system"],
            )
            db.add(role)
            db.flush()

            # Назначить permissions
            for perm_key in role_data["permissions"]:
                perm = permissions[perm_key]
                role_perm = RolePermission(role_id=role.id, permission_id=perm.id)
                db.add(role_perm)

        roles[role_code] = role

    return roles


def seed_users(db: Session, roles: dict[str, Role]) -> None:
    """Создать тестовых пользователей."""
    users_data = [
        {
            "email": "admin@spectech.dev",
            "full_name": "Admin User",
            "password": "admin123",  # pragma: allowlist secret
            "role": "admin",
            "is_superuser": True,
        },
        {
            "email": "manager@spectech.dev",
            "full_name": "Manager User",
            "password": "manager123",  # pragma: allowlist secret
            "role": "manager",
            "is_superuser": False,
        },
        {
            "email": "operator@spectech.dev",
            "full_name": "Operator User",
            "password": "operator123",  # pragma: allowlist secret
            "role": "operator",
            "is_superuser": False,
        },
    ]

    for user_data in users_data:
        user = db.query(User).filter(User.email == user_data["email"]).first()

        if not user:
            # Создать нового пользователя
            user = User(
                email=user_data["email"],
                full_name=user_data["full_name"],
                password_hash=hash_password(user_data["password"]),
                is_superuser=user_data["is_superuser"],
                status=UserStatus.active,
            )
            db.add(user)
            db.flush()
        else:
            # Обновить существующего пользователя
            user.full_name = user_data["full_name"]
            user.is_superuser = user_data["is_superuser"]
            user.status = UserStatus.active

        # Проверить и назначить роль (даже для существующих пользователей)
        role = roles[user_data["role"]]
        existing_role = (
            db.query(UserRole)
            .filter(UserRole.user_id == user.id, UserRole.role_id == role.id)
            .first()
        )

        if not existing_role:
            user_role = UserRole(user_id=user.id, role_id=role.id)
            db.add(user_role)

    db.commit()
    print("✅ Seed data created successfully!")
    print("   - Admin: admin@spectech.dev / admin123")
    print("   - Manager: manager@spectech.dev / manager123")
    print("   - Operator: operator@spectech.dev / operator123")

    db.commit()
    print("✅ Seed data created successfully!")
    print("   - Admin: admin@spectech.dev / admin123")
    print("   - Manager: manager@spectech.dev / manager123")
    print("   - Operator: operator@spectech.dev / operator123")


def seed_vehicles(db: Session) -> None:
    """Создать тестовую технику."""
    from app.models.catalog import Vehicle

    vehicles_data = [
        {
            "id_type": "license_plate",
            "id_value": "А123БВ777",
            "name": "Экскаватор CAT 320D",
            "year": 2020,
            "status": "free",
            "fuel_norm_per_hour": 15.50,
        },
        {
            "id_type": "VIN",
            "id_value": "XTA21099042512345",
            "name": "Самосвал КАМАЗ 65115",
            "year": 2019,
            "status": "busy",
            "fuel_norm_per_100km": 35.00,
        },
        {
            "id_type": "inventory",
            "id_value": "INV-001-2021",
            "name": "Автокран Liebherr LTM 1100",
            "year": 2021,
            "status": "maintenance",
            "fuel_norm_per_hour": 25.00,
        },
    ]

    created_count = 0
    for vehicle_data in vehicles_data:
        existing = db.scalar(
            select(Vehicle).where(Vehicle.id_value == vehicle_data["id_value"])
        )

        if not existing:
            vehicle = Vehicle(**vehicle_data)
            db.add(vehicle)
            created_count += 1

    if created_count > 0:
        db.commit()
        print(f"✅ Created {created_count} test vehicles")
    else:
        print("ℹ️  Test vehicles already exist")


def run_seed(db: Session) -> None:
    """Запустить полный seed процесс."""
    print("🌱 Starting seed data creation...")
    permissions = seed_permissions(db)
    print(f"✅ Created {len(permissions)} permissions")

    roles = seed_roles(db, permissions)
    print(f"✅ Created {len(roles)} roles")

    seed_users(db, roles)
    print("✅ Seed data created successfully!")

    seed_vehicles(db)
    print("✅ Seed data creation completed!")
