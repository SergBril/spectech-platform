from app.models.auth import User
from app.models.rbac import Role, Permission, RolePermission, UserRole
from app.services.rbac_service import (
    check_permission,
    get_user_permissions,
    init_system_data,
)
from app.services.auth_service import hash_password


def setup_test_data(db):
    """Создаёт тестовые роли, права и пользователя."""
    init_system_data(db)
    
    user = User(
        email="rbac_test@test.com",
        full_name="RBAC Test",
        password_hash=hash_password("test123"),
    )
    db.add(user)
    db.flush()
    
    return user


def test_init_system_data(client, db):
    """Системные роли и права инициализируются."""
    init_system_data(db)
    
    roles = db.query(Role).all()
    assert len(roles) >= 6, "Должно быть минимум 6 системных ролей"
    
    permissions = db.query(Permission).all()
    assert len(permissions) >= 10, "Должно быть минимум 10 прав"
    
    admin_role = db.query(Role).filter(Role.code == "admin").first()
    assert admin_role is not None


def test_superuser_has_all_permissions(client, db):
    """Суперпользователь имеет все права."""
    user = setup_test_data(db)
    user.is_superuser = True
    db.commit()
    
    perms = get_user_permissions(db, user)
    assert len(perms) > 0
    assert "vehicles:create" in perms
    assert "rbac:manage" in perms


def test_regular_user_has_no_permissions(client, db):
    """Обычный пользователь без ролей не имеет прав."""
    user = setup_test_data(db)
    db.commit()
    
    perms = get_user_permissions(db, user)
    assert len(perms) == 0


def test_user_with_dispatcher_role_has_dispatcher_permissions(client, db):
    """Пользователь с ролью dispatcher имеет права dispatcher."""
    user = setup_test_data(db)
    
    dispatcher_role = db.query(Role).filter(Role.code == "dispatcher").first()
    assert dispatcher_role is not None, "Роль dispatcher должна существовать"
    
    db.add(UserRole(user_id=user.id, role_id=dispatcher_role.id))
    db.commit()
    
    perms = get_user_permissions(db, user)
    
    # Dispatcher должен иметь эти права
    assert "vehicles:view" in perms, "Dispatcher должен иметь vehicles:view"
    assert "requests:view" in perms, "Dispatcher должен иметь requests:view"
    assert "requests:create" in perms, "Dispatcher должен иметь requests:create"
    assert "shifts:view" in perms, "Dispatcher должен иметь shifts:view"
    
    # Но НЕ должен иметь админские права
    assert "rbac:manage" not in perms, "Dispatcher не должен иметь rbac:manage"


def test_user_with_operator_role_has_limited_permissions(client, db):
    """Пользователь с ролью operator имеет ограниченные права."""
    user = setup_test_data(db)
    
    operator_role = db.query(Role).filter(Role.code == "operator").first()
    assert operator_role is not None
    
    db.add(UserRole(user_id=user.id, role_id=operator_role.id))
    db.commit()
    
    perms = get_user_permissions(db, user)
    
    # Operator должен иметь только базовые права
    assert "vehicles:view" in perms
    assert "shifts:view" in perms
    
    # Но не может создавать/удалять технику
    assert "vehicles:create" not in perms
    assert "vehicles:delete" not in perms


def test_check_permission_superuser(client, db):
    """Проверка прав для суперпользователя."""
    user = setup_test_data(db)
    user.is_superuser = True
    db.commit()
    
    assert check_permission(db, user, "vehicles", "create") is True
    assert check_permission(db, user, "rbac", "manage") is True


def test_check_permission_no_access(client, db):
    """Обычный пользователь не имеет доступа."""
    user = setup_test_data(db)
    db.commit()
    
    assert check_permission(db, user, "vehicles", "create") is False


def test_rbac_roles_endpoint_as_superuser(client, db):
    """Суперпользователь может получить список ролей."""
    from app.api.deps import get_current_user
    from app.main import app
    from app.services.rbac_service import init_system_data
    
    # ВАЖНО: создаём системные роли и права в тестовой БД
    init_system_data(db)
    
    # Регистрация
    client.post("/api/v1/auth/register", json={
        "email": "superadmin@test.com",
        "password": "password123",
        "full_name": "Super Admin Test",
    })
    
    # Получаем пользователя из тестовой БД и делаем суперпользователем
    user = db.query(User).filter(User.email == "superadmin@test.com").first()
    user.is_superuser = True
    db.commit()
    
    # Переопределяем зависимость чтобы всегда возвращать этого суперпользователя
    def override_get_current_user():
        return user
    
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    try:
        # Логин
        response = client.post("/api/v1/auth/login", json={
            "email": "superadmin@test.com",
            "password": "password123",
        })
        assert response.status_code == 200
        token = response.json()["access_token"]
        
        # Получение ролей — теперь в БД есть системные роли
        response = client.get(
            "/api/v1/rbac/roles",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        roles = response.json()
        assert len(roles) >= 6, f"Ожидалось минимум 6 ролей, получено {len(roles)}"
        
        role_codes = [r["code"] for r in roles]
        assert "admin" in role_codes
        assert "dispatcher" in role_codes
        assert "operator" in role_codes
    finally:
        app.dependency_overrides.clear()


def test_rbac_roles_endpoint_regular_user_forbidden(client):
    """Обычный пользователь НЕ может получить список ролей (403)."""
    # Регистрация
    client.post("/api/v1/auth/register", json={
        "email": "regularuser@test.com",
        "password": "password123",
        "full_name": "Regular User",
    })
    
    # Логин
    response = client.post("/api/v1/auth/login", json={
        "email": "regularuser@test.com",
        "password": "password123",
    })
    token = response.json()["access_token"]
    
    # Обычный пользователь должен получить 403
    response = client.get(
        "/api/v1/rbac/roles",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403