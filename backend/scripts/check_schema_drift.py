"""Проверка дрейфа модель↔БД (защита от инцидентов 2026-11-13).

Сравнивает:
  1. Колонки каждой таблицы модели с information_schema.columns.
  2. Члены Python Enum (.name — SQLAlchemy хранит именно имя члена)
     с pg_enum для native-enum колонок.

Запуск (cwd=/app в контейнере или backend/ локально):
    python scripts/check_schema_drift.py

Exit code: 0 — расхождений нет, 1 — обнаружен дрейф, 2 — нет соединения с БД.
CI: отдельный шаг ПОСЛЕ `alembic upgrade head` и ДО запуска тестов.
"""

import importlib
import os
import pkgutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import Enum as SqlEnum  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import SQLAlchemyError  # noqa: E402

from app.core.db import Base, engine  # noqa: E402

# Таблицы, которых легитимно нет в БД (например, создаваемые только тестами).
# Замер 2026-11-13: все 71 таблица моделей присутствуют в БД — список пуст.
EXCLUDED_TABLES: frozenset = frozenset()


def load_all_models() -> None:
    """Импортирует ВСЕ модули app.models (не только __init__), чтобы
    зарегистрировать таблицы в Base.metadata."""
    import app.models as models_pkg

    for module in pkgutil.iter_modules(models_pkg.__path__):
        importlib.import_module(f"app.models.{module.name}")


def diff_sets(model: set, db: set) -> dict:
    """Симметрическая разница наборов имён (чистая функция)."""
    return {
        "model_only": sorted(model - db),
        "db_only": sorted(db - model),
    }


def enum_column_specs(metadata) -> list:
    """(table, column, pg_type_name, expected_names) для native enum-колонок.

    SQLAlchemy хранит .name члена Enum, поэтому ожидаемые значения — имена.
    Для строковых Enum (без enum_class) — значения из type.enums.
    """
    specs = []
    for table in metadata.sorted_tables:
        for column in table.columns:
            ctype = column.type
            if not isinstance(ctype, SqlEnum) or not ctype.native_enum:
                continue
            if ctype.enum_class is not None:
                expected = {member.name for member in ctype.enum_class}
            else:
                expected = set(ctype.enums)
            specs.append((table.name, column.name, ctype.name, expected))
    return specs


def collect_drift(conn, metadata, excluded: frozenset = EXCLUDED_TABLES) -> dict:
    """Собирает отчёт о дрейфе по колонкам, enum'ам и отсутствующим таблицам."""
    db_columns: dict = {}
    db_udt: dict = {}
    for row in conn.execute(
        text(
            "SELECT table_name, column_name, udt_name "
            "FROM information_schema.columns WHERE table_schema = 'public'"
        )
    ):
        db_columns.setdefault(row[0], set()).add(row[1])
        db_udt[(row[0], row[1])] = row[2]

    columns_report = []
    missing_tables = []
    for table in metadata.sorted_tables:
        if table.name in excluded:
            continue
        if table.name not in db_columns:
            missing_tables.append(table.name)
            continue
        diff = diff_sets({c.name for c in table.columns}, db_columns[table.name])
        if diff["model_only"] or diff["db_only"]:
            columns_report.append({"table": table.name, **diff})

    db_enums: dict = {}
    for row in conn.execute(
        text(
            "SELECT t.typname, e.enumlabel FROM pg_enum e "
            "JOIN pg_type t ON t.oid = e.enumtypid"
        )
    ):
        db_enums.setdefault(row[0], set()).add(row[1])

    enums_report = []
    varchar_enums = []
    for table_name, column_name, type_name, expected in enum_column_specs(metadata):
        entry = {"table": table_name, "column": column_name, "type": type_name}
        db_udt_name = db_udt.get((table_name, column_name))
        if db_udt_name is None:
            # колонки нет в БД — покрыто проверкой колонок
            continue
        if db_udt_name != type_name:
            if db_udt_name in db_enums:
                enums_report.append(
                    {
                        **entry,
                        "error": f"тип колонки в БД {db_udt_name} != {type_name}",
                    }
                )
            else:
                # VARCHAR/TEXT: enum хранится строкой, не native enum
                varchar_enums.append(f"{table_name}.{column_name}")
            continue
        if type_name not in db_enums:
            enums_report.append({**entry, "error": "enum-тип отсутствует в pg_enum"})
            continue
        diff = diff_sets(expected, db_enums[type_name])
        if diff["model_only"] or diff["db_only"]:
            enums_report.append({**entry, **diff})

    db_only_tables = sorted(set(db_columns) - set(metadata.tables.keys()))

    return {
        "tables_checked": len(metadata.tables) - len(excluded),
        "missing_tables": sorted(missing_tables),
        "columns": columns_report,
        "enums": enums_report,
        "varchar_enums": sorted(varchar_enums),
        "db_only_tables": db_only_tables,
    }


def format_report(report: dict) -> str:
    """Человекочитаемый отчёт (чистая функция)."""
    lines = ["=== Дрейф модель↔БД ==="]
    lines.append(f"Таблиц моделей проверено: {report['tables_checked']}")

    if report["missing_tables"]:
        lines.append("ОТСУТСТВУЮТ В БД: " + ", ".join(report["missing_tables"]))
    for item in report["columns"]:
        lines.append(
            f"КОЛОНКИ {item['table']}: "
            f"model_only={item['model_only']} db_only={item['db_only']}"
        )
    for item in report["enums"]:
        if "error" in item:
            lines.append(
                f"ENUM {item['table']}.{item['column']} ({item['type']}): "
                f"{item['error']}"
            )
        else:
            lines.append(
                f"ENUM {item['table']}.{item['column']} ({item['type']}): "
                f"model_only={item['model_only']} db_only={item['db_only']}"
            )
    if report.get("varchar_enums"):
        lines.append(
            "Инфо: enum как VARCHAR (не native, сравнение пропущено): "
            + ", ".join(report["varchar_enums"])
        )
    if report["db_only_tables"]:
        lines.append(
            "Инфо: таблицы БД без моделей (legacy/служебные, не дрейф): "
            + ", ".join(report["db_only_tables"])
        )

    has_drift = bool(report["missing_tables"] or report["columns"] or report["enums"])
    lines.append(
        "ИТОГ: ОБНАРУЖЕН ДРЕЙФ (exit 1)"
        if has_drift
        else "ИТОГ: ДРЕЙФ НЕ ОБНАРУЖЕН (exit 0)"
    )
    return "\n".join(lines)


def main() -> int:
    load_all_models()
    try:
        with engine.connect() as conn:
            report = collect_drift(conn, Base.metadata)
    except SQLAlchemyError as exc:
        print(f"Нет соединения с БД: {exc}")
        return 2
    print(format_report(report))
    has_drift = bool(report["missing_tables"] or report["columns"] or report["enums"])
    return 1 if has_drift else 0


if __name__ == "__main__":
    sys.exit(main())
