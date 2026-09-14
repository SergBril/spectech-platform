"""Seed script для создания admin пользователя."""

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models.auth import User
from app.services.auth_service import hash_password


def seed():
    db = SessionLocal()
    try:
        result = db.execute(select(User).where(User.email == "admin@spectech.dev"))
        existing = result.scalar_one_or_none()

        if existing:
            print("✅ Admin уже существует, обновляем пароль")
            existing.password_hash = hash_password("admin123")
            db.commit()
            print(f"✅ Пароль обновлен для {existing.email}")
        else:
            print("🆕 Создаем нового admin пользователя")
            admin = User(
                email="admin@spectech.dev",
                full_name="Главный Админ",
                password_hash=hash_password("admin123"),
                is_superuser=True,
                failed_login_attempts=0,
            )
            db.add(admin)
            db.commit()
            print(f"✅ Admin создан: {admin.email} / admin123")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
