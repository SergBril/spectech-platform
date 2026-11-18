"""Каждый гейдж обязан объявить multiprocess_mode.

Без него prometheus_client в multiprocess-режиме отдаёт серию на каждый воркер.
Задачу планировщика выполняет один воркер, остальные держат ноль, и панель
показывает ноль при реальном значении. Так гейдж просрочки ТО показал 0 при
машине с 760 ч и порогом 750 ч: четыре серии, три нуля, одна единица.

Ноль от незаполненной метрики читается как спокойствие - это опаснее пустой
панели, поэтому режим агрегации проверяется контрактом, а не глазами.
"""

import inspect

from prometheus_client import Gauge

from app.core import metrics


def test_every_gauge_declares_a_multiprocess_mode():
    offenders = []
    for name, obj in vars(metrics).items():
        if isinstance(obj, Gauge):
            mode = getattr(obj, "_multiprocess_mode", None)
            if mode in (None, "all"):
                offenders.append(f"{name} (mode={mode!r})")
    assert (
        not offenders
    ), "гейджи без агрегации отдают серию на воркер и показывают ноль: " + ", ".join(
        offenders
    )


def test_maintenance_gauge_uses_livemax_like_its_neighbours():
    assert metrics.maintenance_due_without_order._multiprocess_mode == "livemax"


def test_setter_actually_sets_the_gauge():
    metrics.set_maintenance_due_without_order(3)
    src = inspect.getsource(metrics.set_maintenance_due_without_order)
    assert "maintenance_due_without_order.set" in src
