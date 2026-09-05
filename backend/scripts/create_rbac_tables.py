import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect

from app.core.db import Base, engine

# Импортируем ВСЕ модели


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
