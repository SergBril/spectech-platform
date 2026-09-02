import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect
from app.core.db import Base, engine
from app.models import *  # noqa: F401, F403


def create_tables():
    print("🔍 Проверка таблиц...")
    inspector = inspect(engine)
    existing = inspector.get_table_names()
    print(f"   Существующих: {len(existing)}")

    print("\n🔨 Создание таблиц телематики...")
    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    final_tables = inspector.get_table_names()
    new_tables = [t for t in final_tables if t not in existing]

    print(f"\n📊 Создано новых таблиц: {len(new_tables)}")
    for table in new_tables:
        print(f"   ✅ {table}")


if __name__ == "__main__":
    create_tables()