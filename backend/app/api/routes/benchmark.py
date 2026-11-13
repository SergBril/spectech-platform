"""Benchmark endpoints for performance testing (superuser only)."""

import asyncio
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.models.auth import User

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


def _require_superuser(current_user: User) -> None:
    """Нагрузочные эндпоинты доступны только superuser (защита от DoS)."""
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Admin only")


@router.get("/fast")
async def benchmark_fast(current_user: User = Depends(get_current_user)):
    """Fast endpoint — baseline performance."""
    _require_superuser(current_user)
    start = time.perf_counter()

    # Минимальная работа
    result = {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

    elapsed = (time.perf_counter() - start) * 1000
    return {**result, "elapsed_ms": round(elapsed, 3)}


@router.get("/cpu")
async def benchmark_cpu(current_user: User = Depends(get_current_user)):
    """CPU-intensive endpoint."""
    _require_superuser(current_user)
    start = time.perf_counter()

    # CPU работа: вычисление простых чисел
    def is_prime(n):
        if n < 2:
            return False
        for i in range(2, int(n**0.5) + 1):
            if n % i == 0:
                return False
        return True

    primes = [n for n in range(2, 1000) if is_prime(n)]

    elapsed = (time.perf_counter() - start) * 1000
    return {
        "status": "ok",
        "primes_found": len(primes),
        "elapsed_ms": round(elapsed, 3),
    }


@router.get("/memory")
async def benchmark_memory(current_user: User = Depends(get_current_user)):
    """Memory-intensive endpoint."""
    _require_superuser(current_user)
    import os

    import psutil

    start = time.perf_counter()

    process = psutil.Process(os.getpid())
    memory_before = process.memory_info().rss / 1024 / 1024  # MB

    # Создаём большой список
    data = [{"id": i, "data": "x" * 100} for i in range(10000)]

    memory_after = process.memory_info().rss / 1024 / 1024
    elapsed = (time.perf_counter() - start) * 1000

    # Освобождаем память
    del data

    return {
        "status": "ok",
        "memory_before_mb": round(memory_before, 2),
        "memory_after_mb": round(memory_after, 2),
        "memory_delta_mb": round(memory_after - memory_before, 2),
        "elapsed_ms": round(elapsed, 3),
    }


@router.get("/async")
async def benchmark_async(current_user: User = Depends(get_current_user)):
    """Async I/O endpoint — simulates parallel tasks."""
    _require_superuser(current_user)
    start = time.perf_counter()

    # Параллельные "задачи" (эмуляция I/O)
    async def fake_io_task(delay: float):
        await asyncio.sleep(delay)
        return {"delay": delay}

    # Запускаем 10 задач параллельно по 50мс каждая
    tasks = [fake_io_task(0.05) for _ in range(10)]
    results = await asyncio.gather(*tasks)

    elapsed = (time.perf_counter() - start) * 1000
    return {
        "status": "ok",
        "tasks_completed": len(results),
        "elapsed_ms": round(elapsed, 3),
        "note": "10 parallel tasks x 50ms each",
    }


@router.get("/summary")
async def benchmark_summary(current_user: User = Depends(get_current_user)):
    """Run all benchmarks and return summary."""
    _require_superuser(current_user)
    results = {}

    # Fast
    start = time.perf_counter()
    for _ in range(100):
        _ = {"status": "ok"}
    results["fast_100_iterations_ms"] = round((time.perf_counter() - start) * 1000, 3)

    # CPU
    start = time.perf_counter()
    sum(i * i for i in range(100000))
    results["cpu_sum_squares_ms"] = round((time.perf_counter() - start) * 1000, 3)

    # Async
    start = time.perf_counter()
    await asyncio.gather(*[asyncio.sleep(0.01) for _ in range(10)])
    results["async_10_sleeps_ms"] = round((time.perf_counter() - start) * 1000, 3)

    return {
        "status": "ok",
        "benchmarks": results,
        "note": "All times in milliseconds",
    }
