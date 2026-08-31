import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect

from app.core.db import Base, engine

# Импортируем ВСЕ модели
from app.models.company import Company
from app.models.auth import User, UserSession
from app.models.catalog import Category, Vehicle
from app.models.contractor import Contractor, Employee, EmployeeCertificate
from app.models.dispatch import Request, RequestStatusLog, RequestAssignment
from app.models.shift import ShiftTask, ShiftReport
from app.models.rbac import Role, Permission, RolePermission, UserRole


def create_tables():
    print("🔍 Проверка существующих таблиц...")
    
    inspector = inspect(engine)
    existing = inspector.get_table_names()
    print(f"   Существующих таблиц: {len(existing)}")
    
    print("\n🔨 Создание недостающих таблиц через SQLAlchemy...")
    Base.metadata.create_all(bind=engine)
    
    print("✅ Готово!")
    
    inspector = inspect(engine)
    final_tables = inspector.get_table_names()
    print(f"\n📊 Итоговый список таблиц ({len(final_tables)} шт):")
    for table in sorted(final_tables):
        marker = "← НОВАЯ" if table not in existing else ""
        print(f"   ✅ {table} {marker}")


if __name__ == "__main__":
    create_tables()