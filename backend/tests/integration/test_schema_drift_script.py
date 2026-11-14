"""Smoke: скрипт дрейфа модель↔БД на реальной БД возвращает 0.

conftest подменяет DATABASE_URL на SQLite в os.environ; исходное окружение
процесса (до подмены) доступно в /proc/self/environ — оттуда берём реальный
DATABASE_URL для subprocess. Вне контейнера/без доступа — skip.

Ожидаемый результат после синхронизации 2026-11-13 (задачи P/T): exit 0.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _original_database_url() -> str | None:
    try:
        raw = Path("/proc/self/environ").read_bytes()
    except OSError:
        return None
    for item in raw.split(b"\0"):
        if item.startswith(b"DATABASE_URL="):
            return item.decode().split("=", 1)[1]
    return None


def test_check_schema_drift_exits_zero():
    db_url = _original_database_url()
    if not db_url or db_url.startswith("sqlite"):
        pytest.skip("нет исходного DATABASE_URL окружения (запуск вне контейнера?)")
    script = BACKEND_ROOT / "scripts" / "check_schema_drift.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        cwd=str(BACKEND_ROOT),
        env={**os.environ, "DATABASE_URL": db_url},
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ДРЕЙФ НЕ ОБНАРУЖЕН" in result.stdout
