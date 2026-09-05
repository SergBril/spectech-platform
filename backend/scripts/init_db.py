import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect

from app.core.db import Base, engine

# Импортируем ВСЕ модели, чтобы они зарегистрировались


def init_database():
    print("🔍 Проверка подключения к БД...")

    # Проверяем что БД доступна
    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()
    print(f"   Существующих таблиц: {len(existing_tables)}")

    if existing_tables:
        print("   Список таблиц:")
        for table in existing_tables:
            print(f"     - {table}")

    print("\n🔨 Создание всех таблиц через SQLAlchemy...")

    # Создаём все таблицы
    Base.metadata.create_all(bind=engine)

    print("✅ Все таблицы успешно созданы!")

    # Проверяем результат
    inspector = inspect(engine)
    final_tables = inspector.get_table_names()
    print(f"\n📊 Итоговый список таблиц ({len(final_tables)} шт):")
    for table in sorted(final_tables):
        print(f"   ✅ {table}")


if __name__ == "__main__":
    init_database()
