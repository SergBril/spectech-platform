"""
🎬 Автоматическая запись демо через OBS + Playwright (упрощённая версия).

Скрипт открывает страницы по прямым URL и показывает результаты API.
OBS записывает весь экран.

Требования:
1. OBS настроен (сцена SpectechDemo + путь записи)
2. Backend запущен
3. Playwright установлен

Запуск:
    python marketing/demo-videos/record_with_obs.py
"""

import asyncio
import os
import subprocess
import time
from pathlib import Path

# === НАСТРОЙКИ ===
OBS_PATH = r"C:\Program Files\obs-studio\bin\64bit\obs64.exe"
BASE_URL = "http://localhost:8000"
VIDEO_DIR = Path(r"C:\Users\osavi\Videos\SpectechDemo")


def check_obs_installed():
    if not os.path.exists(OBS_PATH):
        print(f"❌ OBS не найден: {OBS_PATH}")
        return False
    print("✅ OBS найден")
    return True


def start_obs_recording():
    print("🎥 Запускаю OBS...")
    cmd = [
        OBS_PATH,
        "--startrecording",
        "--minimize-to-tray",
        "--scene",
        "SpectechDemo",
    ]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(5)
    print("✅ OBS записывает")


def stop_obs_recording():
    print("⏹️  Останавливаю OBS...")
    cmd = [OBS_PATH, "--stoprecording"]
    subprocess.run(cmd, capture_output=True)
    time.sleep(3)
    print("✅ Запись остановлена")


async def perform_demo():
    from playwright.async_api import async_playwright

    print("🌐 Запускаю браузер...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--start-maximized", "--disable-infobars"],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
        )
        page = await context.new_page()

        try:
            # === СЦЕНА 1: Заглавный экран (8 сек) ===
            print("🎬 [1/6] Заглавный экран...")
            await page.goto(BASE_URL)
            await page.wait_for_timeout(8000)

            # === СЦЕНА 2: Swagger UI — общий вид (10 сек) ===
            print("🎬 [2/6] Swagger UI...")
            await page.goto(f"{BASE_URL}/docs")
            await page.wait_for_timeout(10000)

            # === СЦЕНА 3: Публичный каталог компаний (15 сек) ===
            print("🎬 [3/6] Публичный каталог компаний...")
            await page.goto(f"{BASE_URL}/docs")
            await page.wait_for_timeout(2000)

            # Используем CSS-селектор по data-path (надёжнее чем text)
            try:
                # Ищем endpoint по атрибуту data-path
                companies_btn = page.locator(
                    '[data-path="/api/v1/public/companies"]'
                ).first
                await companies_btn.click(timeout=10000)
                await page.wait_for_timeout(1000)

                # Try it out
                try_it_btn = page.locator(".try-out__btn").first
                await try_it_btn.click()
                await page.wait_for_timeout(500)

                # Execute
                execute_btn = page.locator(".execute.opblock-control__btn").first
                await execute_btn.click()
                await page.wait_for_timeout(8000)
            except Exception as e:
                print(f"   ⚠️  Не удалось кликнуть: {e}")
                print("   Продолжаю без этого шага...")
                await page.wait_for_timeout(10000)

            # === СЦЕНА 4: Публичный каталог техники (15 сек) ===
            print("🎬 [4/6] Публичный каталог техники...")
            await page.goto(f"{BASE_URL}/docs")
            await page.wait_for_timeout(2000)

            try:
                vehicles_btn = page.locator(
                    '[data-path="/api/v1/public/vehicles"]'
                ).first
                await vehicles_btn.click(timeout=10000)
                await page.wait_for_timeout(1000)

                try_it_btn = page.locator(".try-out__btn").first
                await try_it_btn.click()
                await page.wait_for_timeout(500)

                execute_btn = page.locator(".execute.opblock-control__btn").first
                await execute_btn.click()
                await page.wait_for_timeout(8000)
            except Exception as e:
                print(f"   ⚠️  Не удалось кликнуть: {e}")
                await page.wait_for_timeout(10000)

            # === СЦЕНА 5: Чат по заявке (15 сек) ===
            print("🎬 [5/6] Чат по заявке...")
            await page.goto(f"{BASE_URL}/docs")
            await page.wait_for_timeout(2000)

            try:
                chat_btn = page.locator(
                    '[data-path="/api/v1/chat/requests/{request_id}"]'
                ).first
                await chat_btn.click(timeout=10000)
                await page.wait_for_timeout(1000)

                try_it_btn = page.locator(".try-out__btn").first
                await try_it_btn.click()
                await page.wait_for_timeout(500)

                # Вводим request_id = 7
                request_id_input = page.locator('input[placeholder="request_id"]').first
                await request_id_input.fill("7")
                await page.wait_for_timeout(500)

                execute_btn = page.locator(".execute.opblock-control__btn").first
                await execute_btn.click()
                await page.wait_for_timeout(8000)
            except Exception as e:
                print(f"   ⚠️  Не удалось кликнуть: {e}")
                await page.wait_for_timeout(10000)

            # === СЦЕНА 6: Финальный экран (8 сек) ===
            print("🎬 [6/6] Финальный экран...")
            await page.goto(BASE_URL)
            await page.wait_for_timeout(8000)

        except Exception as e:
            print(f"❌ Ошибка: {e}")
        finally:
            await browser.close()


def list_videos():
    print("\n" + "=" * 60)
    print("📹 Проверка папок с видео:")
    print("=" * 60)

    folders = [
        VIDEO_DIR,
        Path(r"C:\Users\osavi\Videos"),
        Path(r"C:\Users\osavi\Documents"),
    ]

    found = False
    for folder in folders:
        if folder.exists():
            videos = list(folder.glob("*.mp4")) + list(folder.glob("*.mkv"))
            if videos:
                print(f"\n📂 {folder}:")
                for v in sorted(videos, key=lambda p: p.stat().st_mtime, reverse=True)[
                    :3
                ]:
                    size_mb = v.stat().st_size / (1024 * 1024)
                    print(f"   📹 {v.name} ({size_mb:.1f} MB)")
                found = True

    if not found:
        print("\n⚠️  Видео не найдены!")
        print("   Проверьте настройки OBS:")
        print("   1. Откройте OBS")
        print("   2. Настройки → Вывод → Запись")
        print("   3. Убедитесь, что путь указан правильно")
        print("   4. Попробуйте записать тестовое видео вручную")


def main():
    print("=" * 60)
    print("🎬 SpectechPlatform — Запись демо")
    print("=" * 60)

    if not check_obs_installed():
        return

    VIDEO_DIR.mkdir(parents=True, exist_ok=True)

    print("\n⚠️  ВАЖНО перед запуском:")
    print("   1. OBS настроен (сцена SpectechDemo создана)")
    print("   2. Путь записи в OBS: C:\\Users\\osavi\\Videos\\SpectechDemo\\")
    print("   3. OBS закрыт")
    print("   4. Уведомления Windows отключены")
    print("\n⏳ Старт через 5 секунд... (Ctrl+C для отмены)")

    try:
        for i in range(5, 0, -1):
            print(f"   {i}...")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n❌ Отменено")
        return

    start_obs_recording()

    try:
        asyncio.run(perform_demo())
        print("\n⏳ Финальная пауза 5 секунд...")
        time.sleep(5)
    except KeyboardInterrupt:
        print("\n⚠️  Прервано")
    finally:
        stop_obs_recording()

    list_videos()

    print("\n" + "=" * 60)
    print("🎉 ГОТОВО!")
    print("=" * 60)


if __name__ == "__main__":
    main()
