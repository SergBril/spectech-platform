"""Слушатель событий планировщика должен считать провалы и пропуски раздельно.

APScheduler рапортует "executed successfully", если задача проглотила исключение,
поэтому нерабочая разноска платежей жила незамеченной. Слушатель делает отказ
явным, а счётчики - видимыми в Prometheus.

События здесь НАСТОЯЩИЕ объекты APScheduler, не самодельные заглушки: мок принял
бы атрибуты, которых у реального события нет, и тест прошёл бы на вымысле.
"""

import os

from apscheduler.events import (
    EVENT_JOB_ERROR,
    EVENT_JOB_EXECUTED,
    EVENT_JOB_MISSED,
    JobExecutionEvent,
    JobSubmissionEvent,
)


def _counter(name: str, job_id: str) -> float:
    from prometheus_client import REGISTRY, CollectorRegistry, generate_latest

    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        from prometheus_client.multiprocess import MultiProcessCollector

        reg = CollectorRegistry()
        MultiProcessCollector(reg)
        text = generate_latest(reg).decode()
    else:
        text = generate_latest(REGISTRY).decode()
    for line in text.split("\n"):
        if line.startswith(name + "{") and f'job_id="{job_id}"' in line:
            return float(line.rsplit(" ", 1)[1])
    return 0.0


def _error_event(job_id: str) -> JobExecutionEvent:
    try:
        raise RuntimeError("задача упала")
    except RuntimeError as exc:
        return JobExecutionEvent(
            EVENT_JOB_ERROR, job_id, "default", None, None, exc, exc.__traceback__
        )


def test_failure_increments_only_failures():
    from app.tasks.scheduler import _on_scheduler_job_event

    job_id = "probe_failure_job"
    before_f = _counter("scheduler_job_failures_total", job_id)
    before_m = _counter("scheduler_job_missed_total", job_id)

    _on_scheduler_job_event(_error_event(job_id))

    assert _counter("scheduler_job_failures_total", job_id) == before_f + 1
    assert _counter("scheduler_job_missed_total", job_id) == before_m


def test_missed_increments_only_missed():
    from app.tasks.scheduler import _on_scheduler_job_event

    job_id = "probe_missed_job"
    before_f = _counter("scheduler_job_failures_total", job_id)
    before_m = _counter("scheduler_job_missed_total", job_id)

    _on_scheduler_job_event(JobSubmissionEvent(EVENT_JOB_MISSED, job_id, "default", []))

    assert _counter("scheduler_job_missed_total", job_id) == before_m + 1
    assert _counter("scheduler_job_failures_total", job_id) == before_f


def test_successful_execution_counts_as_neither():
    """Успех не должен попадать ни в провалы, ни в пропуски.

    Прежняя ветка else считала пропуском любое событие без исключения, и
    EVENT_JOB_EXECUTED поднимал счётчик пропусков. Маска регистрации сейчас это
    исключает, но счётчик не должен зависеть от того, кто расширит маску.
    """
    from app.tasks.scheduler import _on_scheduler_job_event

    job_id = "probe_success_job"
    before_f = _counter("scheduler_job_failures_total", job_id)
    before_m = _counter("scheduler_job_missed_total", job_id)

    _on_scheduler_job_event(
        JobExecutionEvent(EVENT_JOB_EXECUTED, job_id, "default", None, "ok")
    )

    assert _counter("scheduler_job_failures_total", job_id) == before_f
    assert _counter("scheduler_job_missed_total", job_id) == before_m


def test_listener_is_registered_for_errors_and_misses_only():
    """Маска регистрации - часть контракта: успех не должен доходить до счётчиков."""
    import pathlib
    import re

    src = pathlib.Path(__file__).resolve().parents[2] / "app" / "tasks" / "scheduler.py"
    text = src.read_text(encoding="utf-8-sig")
    masks = re.findall(r"add_listener\(_on_scheduler_job_event,([^)]*)\)", text)
    assert masks, "слушатель не зарегистрирован"
    mask = masks[0]
    assert "EVENT_JOB_ERROR" in mask and "EVENT_JOB_MISSED" in mask
    assert "EVENT_JOB_EXECUTED" not in mask
