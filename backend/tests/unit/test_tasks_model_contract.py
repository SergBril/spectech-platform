"""Контракт моделей для всех модулей задач.

Пять ежедневных задач планировщика никогда не исполнялись: обращались к
несуществующим колонкам (Invoice.payer_inn), сравнивали статусы со значениями
вне enum и ждали синхронную сессию. Моки этого не ловили - MagicMock принимает
любой атрибут. Проверка идёт по AST против реальных моделей и их enum.

Инструмент проверен саботажем: проба с четырьмя известными дефектами даёт
ровно четыре находки. Без такой проверки «ноль проблем» означало бы лишь то,
что проверка ничего не проверяет.
"""

import ast
import enum
import importlib
import pathlib
import pkgutil

import pytest
from sqlalchemy import Enum as SAEnum

import app.models as models_pkg

TASKS_DIR = pathlib.Path(__file__).resolve().parents[2] / "app" / "tasks"


def _load_model_metadata():
    columns, col_enums = {}, {}
    for m in pkgutil.iter_modules(models_pkg.__path__):
        try:
            mod = importlib.import_module(f"app.models.{m.name}")
        except Exception:
            continue
        for name in dir(mod):
            obj = getattr(mod, name)
            if hasattr(obj, "__tablename__") and hasattr(obj, "__table__"):
                columns[name] = {c.key for c in obj.__table__.columns}
                for c in obj.__table__.columns:
                    if isinstance(c.type, SAEnum):
                        col_enums[(name, c.key)] = set(c.type.enums)
                        continue
                    try:
                        pt = c.type.python_type
                    except Exception:
                        continue
                    if isinstance(pt, type) and issubclass(pt, enum.Enum):
                        col_enums[(name, c.key)] = {e.value for e in pt}
    return columns, col_enums


COLUMNS, COL_ENUMS = _load_model_metadata()
NON_COLUMN_ATTRS = {"query", "metadata", "dict", "copy"}
SYNC_SESSION_NAMES = {"db", "session", "s"}
SYNC_METHODS = {"execute", "commit", "flush", "refresh", "scalar", "scalars"}


def audit_source(source: str, uses_async_session: bool = False):
    problems = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            cls = node.value.id
            if (
                cls in COLUMNS
                and node.attr not in COLUMNS[cls]
                and not node.attr.startswith("__")
                and node.attr not in NON_COLUMN_ATTRS
            ):
                problems.append(
                    f"{cls}.{node.attr} - нет такой колонки (line {node.lineno})"
                )

        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Attribute):
            owner = node.left.value
            cls = owner.id if isinstance(owner, ast.Name) else None
            key = (cls, node.left.attr)
            if key in COL_ENUMS:
                for cmp in node.comparators:
                    if isinstance(cmp, ast.Constant) and isinstance(cmp.value, str):
                        if cmp.value not in COL_ENUMS[key]:
                            problems.append(
                                f"{cls}.{key[1]} == {cmp.value!r} вне enum (line {node.lineno})"
                            )

        # Model.status.in_([...]) - частый паттерн в задачах
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("in_", "not_in", "notin_")
            and isinstance(node.func.value, ast.Attribute)
            and isinstance(node.func.value.value, ast.Name)
        ):
            key = (node.func.value.value.id, node.func.value.attr)
            if key in COL_ENUMS and node.args:
                arg = node.args[0]
                if isinstance(arg, ast.List | ast.Tuple | ast.Set):
                    for el in arg.elts:
                        if isinstance(el, ast.Constant) and isinstance(el.value, str):
                            if el.value not in COL_ENUMS[key]:
                                problems.append(
                                    f"{key[0]}.{key[1]}.in_ содержит {el.value!r} вне enum (line {node.lineno})"
                                )

        if (
            not uses_async_session
            and isinstance(node, ast.Await)
            and isinstance(node.value, ast.Call)
        ):
            f = node.value.func
            if (
                isinstance(f, ast.Attribute)
                and f.attr in SYNC_METHODS
                and isinstance(f.value, ast.Name)
                and f.value.id in SYNC_SESSION_NAMES
            ):
                problems.append(
                    f"await {f.value.id}.{f.attr}() на синхронной сессии (line {node.lineno})"
                )
    return problems


def test_metadata_was_loaded():
    """Без моделей проверка пуста и всегда зелена."""
    assert len(COLUMNS) > 20, f"загружено только {len(COLUMNS)} моделей"
    assert len(COL_ENUMS) > 10, f"загружено только {len(COL_ENUMS)} enum-колонок"


def test_audit_catches_known_defects():
    """Саботаж: инструмент обязан находить то, ради чего написан."""
    probe = (
        "from app.models.finance import Invoice\n"
        "from app.models.telematics import Alert\n"
        "async def bad(db):\n"
        "    a = Invoice.payer_inn\n"
        "    b = Invoice.status == 'active'\n"
        "    c = Alert.severity == 'high'\n"
        "    d = Invoice.status.in_(['draft', 'nonexistent_status'])\n"
        "    await db.execute(1)\n"
    )
    found = audit_source(probe)
    assert len(found) == 5, f"ожидалось 5 находок, получено {len(found)}: {found}"


@pytest.mark.parametrize("path", sorted(TASKS_DIR.glob("*.py")), ids=lambda p: p.name)
def test_task_module_respects_model_contract(path):
    source = path.read_text(encoding="utf-8-sig")
    uses_async = "AsyncSession" in source or "async_session_maker" in source
    problems = audit_source(source, uses_async_session=uses_async)
    assert not problems, f"{path.name}:\n" + "\n".join(problems)
