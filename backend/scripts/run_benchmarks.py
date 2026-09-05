"""
Автоматический бенчмарк всех /benchmark endpoints.
Собирает статистику и создаёт отчёт.
"""

import statistics
import time
from datetime import datetime

"""
Автоматический бенчмарк всех /benchmark endpoints.
Собирает статистику и создаёт отчёт.
"""
import statistics
import time
from datetime import datetime

import requests

# Используем IP вместо hostname чтобы избежать DNS и IPv6 проблем
BASE_URL = "http://127.0.0.1:8000/api/v1/benchmark"
ITERATIONS = 20  # Количество прогонов каждого теста
WARMUP_REQUESTS = 3  # Прогревочные запросы (не учитываются)

# Session для connection pooling (переиспользует TCP соединение)
session = requests.Session()


def run_benchmark(name: str, url: str, iterations: int = ITERATIONS) -> dict:
    """Запускает бенчмарк несколько раз и собирает статистику."""
    times = []
    last_result = None

    # Прогревочные запросы (TCP + Python cache warm-up)
    for _ in range(WARMUP_REQUESTS):
        try:
            session.get(url, timeout=10)
        except Exception:
            pass

    for _ in range(iterations):
        start = time.perf_counter()
        try:
            response = session.get(url, timeout=10)
            response.raise_for_status()
            elapsed_ms = (time.perf_counter() - start) * 1000
            times.append(elapsed_ms)
            last_result = response.json()
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
            return {"error": str(e)}

    return {
        "name": name,
        "iterations": iterations,
        "min_ms": round(min(times), 3),
        "max_ms": round(max(times), 3),
        "avg_ms": round(statistics.mean(times), 3),
        "median_ms": round(statistics.median(times), 3),
        "p95_ms": round(sorted(times)[int(len(times) * 0.95)], 3),
        "stdev_ms": round(statistics.stdev(times), 3) if len(times) > 1 else 0,
        "last_response": last_result,
    }


def print_report(results: list) -> None:
    """Печатает красивый отчёт."""
    print("\n" + "=" * 80)
    print("📊 BENCHMARK REPORT")
    print(f"📅 Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔄 Итераций на тест: {ITERATIONS}")
    print("=" * 80)

    # Заголовок таблицы
    print(
        f"\n{'Endpoint':<20} {'Min':>8} {'Avg':>8} {'Median':>8} "
        f"{'P95':>8} {'Max':>8} {'StdDev':>8}"
    )
    print("-" * 80)

    for r in results:
        if "error" in r:
            print(f"{r['name']:<20} ERROR: {r['error']}")
            continue

        print(
            f"{r['name']:<20} "
            f"{r['min_ms']:>7.2f} "
            f"{r['avg_ms']:>7.2f} "
            f"{r['median_ms']:>7.2f} "
            f"{r['p95_ms']:>7.2f} "
            f"{r['max_ms']:>7.2f} "
            f"{r['stdev_ms']:>7.2f}"
        )

    print("-" * 80)
    print("Все значения в миллисекундах (мс)\n")

    # Анализ производительности
    print("📈 АНАЛИЗ:")
    for r in results:
        if "error" in r:
            continue

        if r["avg_ms"] < 5:
            grade = "⚡ Отлично (<5мс)"
        elif r["avg_ms"] < 50:
            grade = "✅ Хорошо (<50мс)"
        elif r["avg_ms"] < 200:
            grade = "⚠️  Приемлемо (<200мс)"
        else:
            grade = "🐢 Требует оптимизации (>200мс)"

        print(f"  {r['name']:<20} {grade}")

    print("\n" + "=" * 80)


def save_report(results: list, filename: str = "benchmark_report.txt") -> None:
    """Сохраняет отчёт в файл."""
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"Benchmark Report - {datetime.now().isoformat()}\n")
        f.write(f"Iterations per test: {ITERATIONS}\n")
        f.write("=" * 80 + "\n\n")

        for r in results:
            if "error" in r:
                f.write(f"{r['name']}: ERROR - {r['error']}\n")
                continue

            f.write(f"\n{r['name']}:\n")
            f.write(f"  Iterations: {r['iterations']}\n")
            f.write(f"  Min:    {r['min_ms']:.3f} ms\n")
            f.write(f"  Avg:    {r['avg_ms']:.3f} ms\n")
            f.write(f"  Median: {r['median_ms']:.3f} ms\n")
            f.write(f"  P95:    {r['p95_ms']:.3f} ms\n")
            f.write(f"  Max:    {r['max_ms']:.3f} ms\n")
            f.write(f"  StdDev: {r['stdev_ms']:.3f} ms\n")
            f.write(f"  Last response: {r['last_response']}\n")

    print(f"💾 Отчёт сохранён в: {filename}")


def main():
    """Главная функция."""
    print("🚀 Запуск автоматических бенчмарков...")
    print(f"📡 Target: {BASE_URL}")

    # Проверяем что сервер запущен
    try:
        requests.get(f"{BASE_URL}/fast", timeout=5)
        print("✅ Сервер доступен")
    except requests.ConnectionError:
        print("❌ Сервер не запущен! Запустите: uvicorn app.main:app --reload")
        return

    # Список бенчмарков
    benchmarks = [
        ("fast", f"{BASE_URL}/fast"),
        ("cpu", f"{BASE_URL}/cpu"),
        ("memory", f"{BASE_URL}/memory"),
        ("async", f"{BASE_URL}/async"),
        ("summary", f"{BASE_URL}/summary"),
    ]

    # Запускаем все бенчмарки
    results = []
    for name, url in benchmarks:
        print(f"\n▶ Запуск: /benchmark/{name}...")
        result = run_benchmark(name, url)
        results.append(result)

        if "error" not in result:
            print(f"  ✓ Avg: {result['avg_ms']} мс")

    # Печатаем и сохраняем отчёт
    print_report(results)
    save_report(results)

    print("\n🎉 Бенчмарк завершён!")


if __name__ == "__main__":
    main()
