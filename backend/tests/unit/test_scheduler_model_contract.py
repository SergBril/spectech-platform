"""Задачи планировщика должны обращаться к существующим полям моделей.

Пять задач были написаны против вымышленных полей: Vehicle.is_active,
EngineHoursLog.total_hours и recorded_at, ShiftTask.planned_start,
Invoice.total_amount, плюс значения enum "pending" и "approved", которых в
document_status нет. Каждая падала при каждом запуске, а await db.close() в
finally замещал настоящую причину бессмысленным TypeError.

Тест сверяет ВСЕ обращения Модель.атрибут в scheduler.py с реальными моделями.
Он ловит класс дефекта, а не пять конкретных опечаток.
"""

import importlib
import re
from pathlib import Path

SCHEDULER = Path(__file__).resolve().parents[2] / "app" / "tasks" / "scheduler.py"


def _imported_models(source: str) -> dict:
    models = {}
    for module, names in re.findall(
        r"from (app\.models[\w.]*) import ([^\n]+)", source
    ):
        mod = importlib.import_module(module)
        for name in re.split(r"[,\s]+", names.strip()):
            name = name.strip("()")
            if name and hasattr(mod, name):
                models[name] = getattr(mod, name)
    return models


def test_every_model_attribute_referenced_by_a_job_exists():
    source = SCHEDULER.read_text(encoding="utf-8")
    models = _imported_models(source)
    assert models, "не удалось собрать модели из импортов scheduler.py"

    missing = []
    for cls, attr in sorted(
        set(re.findall(r"\b([A-Z][A-Za-z]+)\.([a-z_][a-z_0-9]*)\b", source))
    ):
        if cls in models and not hasattr(models[cls], attr):
            missing.append(f"{cls}.{attr}")

    assert not missing, f"задачи обращаются к несуществующим полям: {missing}"


def test_no_await_on_the_sync_session():
    """SessionLocal синхронный: await на его вызовах падает.

    Await db.close() в finally к тому же замещает исходное исключение,
    превращая внятную ошибку в "NoneType can't be used in await".
    """
    source = SCHEDULER.read_text(encoding="utf-8")
    code = "\n".join(
        line for line in source.split("\n") if not line.lstrip().startswith("#")
    )
    offenders = re.findall(r"await (db\.\w+)", code)
    assert not offenders, f"await на синхронной сессии: {sorted(set(offenders))}"


def test_enum_values_used_in_filters_exist():
    """Литералы статусов сверяются с enum КОНКРЕТНОЙ модели.

    У ShiftTask свой shift_task_status (planned, completed, ...), у Invoice,
    Payout и Act - document_status. Первая версия этого теста приписывала всем
    моделям document_status и кричала на корректный ShiftTask.status ==
    "completed". Тест, который падает на правильном коде, приучает игнорировать
    красный, поэтому проверка идёт по типу колонки каждой модели.
    """
    from sqlalchemy import inspect

    source = SCHEDULER.read_text(encoding="utf-8")
    models = _imported_models(source)

    allowed = {}
    for name, model in models.items():
        # В импортах есть и enum-классы (DocumentStatus, MatchStatus) -
        # инспектировать их как модели нельзя.
        if not hasattr(model, "__tablename__"):
            continue
        cols = inspect(model).columns
        if "status" not in cols:
            continue
        enums = getattr(cols["status"].type, "enums", None)
        if enums:
            allowed[name] = set(enums)

    assert allowed, "не удалось получить enum статусов ни для одной модели"

    bad = []
    for cls, value in re.findall(r'\b(\w+)\.status\s*==\s*"([a-z_]+)"', source):
        if cls in allowed and value not in allowed[cls]:
            bad.append(f'{cls}.status == "{value}"')

    for cls, group in re.findall(r"\b(\w+)\.status\.in_\(\[([^\]]+)\]\)", source):
        if cls not in allowed:
            continue
        for value in re.findall(r'"([a-z_]+)"', group):
            if value not in allowed[cls]:
                bad.append(f'{cls}.status.in_([... "{value}" ...])')

    assert not bad, f"значения вне enum соответствующей модели: {sorted(set(bad))}"
