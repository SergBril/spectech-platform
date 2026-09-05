"""Benchmark endpoints for performance testing."""

import asyncio
import time
from datetime import datetime

from fastapi import APIRouter

router = APIRouter(prefix="/benchmark", tags=["benchmark"])


@router.get("/fast")
async def benchmark_fast():
    """Fast endpoint — baseline performance."""
    start = time.perf_counter()

    # Минимальная работа
    result = {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

    elapsed = (time.perf_counter() - start) * 1000
    return {**result, "elapsed_ms": round(elapsed, 3)}


@router.get("/cpu")
async def benchmark_cpu():
    """CPU-intensive endpoint."""
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
async def benchmark_memory():
    """Memory-intensive endpoint."""
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
async def benchmark_async():
    """Async I/O endpoint — simulates parallel tasks."""
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
async def benchmark_summary():
    """Run all benchmarks and return summary."""
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
