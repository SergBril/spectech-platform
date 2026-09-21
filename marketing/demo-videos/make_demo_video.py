"""
🎬 Автоматическое демо-видео SpectechPlatform.

Надёжная версия через FFmpeg напрямую (без MoviePy).

Принцип:
1. Pillow создаёт title/final экраны
2. Playwright делает скриншоты API
3. edge-tts генерирует озвучку (ru-RU-DmitryNeural)
4. FFmpeg напрямую собирает видео через concat demuxer

Запуск:
    python marketing/demo-videos/make_demo_video.py
"""

import asyncio
import subprocess
from datetime import datetime
from pathlib import Path

# === ПУТИ ===
SCRIPT_DIR = Path(__file__).parent
OUTPUT_DIR = SCRIPT_DIR / "output"
SCREENSHOTS_DIR = OUTPUT_DIR / "screenshots"
AUDIO_DIR = OUTPUT_DIR / "audio"
CLIPS_DIR = OUTPUT_DIR / "clips"
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
FINAL_VIDEO = OUTPUT_DIR / f"SpectechPlatform_Demo_{TIMESTAMP}.mp4"

# === НАСТРОЙКИ ===
BASE_URL = "http://localhost:8000"
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
FPS = 24
VOICE = "ru-RU-DmitryNeural"

# Получаем путь к ffmpeg через imageio-ffmpeg
try:
    import imageio_ffmpeg

    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG_PATH = "ffmpeg"  # fallback


# === СЦЕНАРИЙ ===
DEMO_STEPS = [
    {
        "name": "01_title",
        "type": "title",
        "title": "SpectechPlatform",
        "subtitle": "Маркетплейс спецтехники\nс real-time чатом",
        "emoji": "🚜",
        "voiceover": (
            "СпекТех Платформа — маркетплейс спецтехники "
            "с чатом в реальном времени. "
            "Смотрите демонстрацию за две минуты."
        ),
    },
    {
        "name": "02_swagger",
        "type": "url",
        "url": f"{BASE_URL}/docs",
        "voiceover": (
            "Платформа построена на современном стеке: "
            "ФастАПИ, Постгрес, Докер. "
            "Более ста пятидесяти АПИ-эндпоинтов для управления "
            "парком спецтехники."
        ),
    },
    {
        "name": "03_auth",
        "type": "url",
        "url": f"{BASE_URL}/docs#/🔐 Auth (Аутентификация)",
        "voiceover": (
            "Безопасная аутентификация через JWT-токены. "
            "Ролевая модель доступа с гранулярными правами "
            "для диспетчеров, операторов и руководителей."
        ),
    },
    {
        "name": "04_requests",
        "type": "url",
        "url": f"{BASE_URL}/docs#/📋 Requests (Заявки)",
        "voiceover": (
            "Диспетчеризация заявок с полным жизненным циклом. "
            "От создания до закрытия акта. "
            "Автоматическое назначение техники и операторов."
        ),
    },
    {
        "name": "05_marketplace",
        "type": "url",
        "url": f"{BASE_URL}/docs#/🎯 Marketplace (Отклики на заявки)",
        "voiceover": (
            "Маркетплейс откликов на заявки. "
            "Владельцы техники предлагают свои машины. "
            "Один клик — и техника назначена на объект."
        ),
    },
    {
        "name": "06_chat",
        "type": "url",
        "url": f"{BASE_URL}/docs#/💬 Chat (Чат по заявке)",
        "voiceover": (
            "Чат в реальном времени по каждой заявке. "
            "Заказчик и владелец согласовывают детали "
            "без звонков и электронной почты."
        ),
    },
    {
        "name": "07_telematics",
        "type": "url",
        "url": f"{BASE_URL}/docs#/🛰️ Telematics (Телематика)",
        "voiceover": (
            "Телематика и GPS-мониторинг. "
            "Контроль топлива, геозоны, автоматическое "
            "определение сливов и простоев."
        ),
    },
    {
        "name": "08_final",
        "type": "title",
        "title": "spectehpro.ru",
        "subtitle": "Автоматизируйте работу\nсо спецтехникой",
        "emoji": "🚀",
        "voiceover": (
            "СпекТех Про — автоматизируйте работу со спецтехникой. "
            "Регистрируйтесь на сайте спектехпро точка ру."
        ),
    },
]


def ensure_dirs():
    """Создаёт директории."""
    for d in [OUTPUT_DIR, SCREENSHOTS_DIR, AUDIO_DIR, CLIPS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def create_title_image(step: dict, output_path: Path):
    """Создаёт красивый title/final экран через Pillow."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT))
    draw = ImageDraw.Draw(img)

    # Градиентный фон
    for y in range(VIDEO_HEIGHT):
        ratio = y / VIDEO_HEIGHT
        r = int(26 * (1 - ratio) + 1 * ratio)
        g = int(35 * (1 - ratio) + 87 * ratio)
        b = int(126 * (1 - ratio) + 155 * ratio)
        draw.line([(0, y), (VIDEO_WIDTH, y)], fill=(r, g, b))

    # Пытаемся загрузить шрифты
    try:
        # Windows шрифты
        title_font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 120)
        subtitle_font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 48)
        emoji_font = ImageFont.truetype("C:/Windows/Fonts/seguisym.ttf", 150)
    except Exception:
        try:
            title_font = ImageFont.truetype("arial.ttf", 120)
            subtitle_font = ImageFont.truetype("arial.ttf", 48)
            emoji_font = ImageFont.truetype("arial.ttf", 150)
        except Exception:
            title_font = ImageFont.load_default()
            subtitle_font = ImageFont.load_default()
            emoji_font = ImageFont.load_default()

    # Emoji сверху
    try:
        emoji_bbox = draw.textbbox((0, 0), step["emoji"], font=emoji_font)
        emoji_w = emoji_bbox[2] - emoji_bbox[0]
        draw.text(
            ((VIDEO_WIDTH - emoji_w) / 2, 250),
            step["emoji"],
            fill=(255, 255, 255),
            font=emoji_font,
        )
    except Exception:
        pass

    # Title
    try:
        title_bbox = draw.textbbox((0, 0), step["title"], font=title_font)
        title_w = title_bbox[2] - title_bbox[0]
        draw.text(
            ((VIDEO_WIDTH - title_w) / 2, 450),
            step["title"],
            fill=(255, 255, 255),
            font=title_font,
        )
    except Exception:
        draw.text((100, 450), step["title"], fill=(255, 255, 255))

    # Subtitle (многострочный)
    try:
        y_pos = 650
        for line in step["subtitle"].split("\n"):
            sub_bbox = draw.textbbox((0, 0), line, font=subtitle_font)
            sub_w = sub_bbox[2] - sub_bbox[0]
            draw.text(
                ((VIDEO_WIDTH - sub_w) / 2, y_pos),
                line,
                fill=(220, 220, 255),
                font=subtitle_font,
            )
            y_pos += 70
    except Exception:
        draw.text((100, 650), step["subtitle"], fill=(220, 220, 255))

    img.save(output_path)
    print(f"   🎨 Title: {output_path.name}")


async def take_screenshots():
    """Делает скриншоты через Playwright."""
    from playwright.async_api import async_playwright

    print("\n📸 Делаю скриншоты...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": VIDEO_WIDTH, "height": VIDEO_HEIGHT},
            locale="ru-RU",
        )
        page = await context.new_page()

        for step in DEMO_STEPS:
            screenshot_path = SCREENSHOTS_DIR / f"{step['name']}.png"

            if step["type"] == "title":
                create_title_image(step, screenshot_path)
                continue

            # URL-скриншоты
            try:
                await page.goto(
                    step["url"], timeout=15000, wait_until="domcontentloaded"
                )
                await page.wait_for_timeout(2000)

                # Прокрутка
                await page.evaluate("window.scrollTo(0, 200)")
                await page.wait_for_timeout(500)

            except Exception as e:
                print(f"   ⚠️  {step['name']}: {type(e).__name__}")
                # Fallback: создаём простой title с названием
                fallback_step = {
                    "title": step["name"].replace("_", " ").title(),
                    "subtitle": "SpectechPlatform API",
                    "emoji": "🔧",
                }
                create_title_image(fallback_step, screenshot_path)
                continue

            await page.screenshot(path=str(screenshot_path), full_page=False)
            print(f"   📸 {screenshot_path.name}")

        await browser.close()


async def generate_voiceover(text: str, output_path: Path, max_retries: int = 3):
    """Генерирует озвучку с retry."""
    import edge_tts

    for attempt in range(1, max_retries + 1):
        try:
            communicate = edge_tts.Communicate(text, VOICE, rate="-5%")
            await communicate.save(str(output_path))
            if output_path.exists() and output_path.stat().st_size > 1000:
                print(f"   🗣️  {output_path.name}")
                return
        except Exception:
            if attempt < max_retries:
                print(f"   ⏳ Retry {attempt}...")
                import time

                time.sleep(2**attempt)

    # Fallback: pyttsx3
    try:
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", 150)
        engine.save_to_file(text, str(output_path))
        engine.runAndWait()
        print(f"   🗣️  {output_path.name} (fallback)")
    except Exception:
        print(f"   ❌ Не удалось создать {output_path.name}")


async def generate_all_voiceovers():
    """Генерирует озвучку для всех шагов."""
    print("\n🗣️  Генерирую озвучку...")
    for step in DEMO_STEPS:
        audio_path = AUDIO_DIR / f"{step['name']}.mp3"
        await generate_voiceover(step["voiceover"], audio_path)


def get_audio_duration(audio_path: Path) -> float:
    """Получает длительность аудио через ffprobe."""
    # imageio-ffmpeg не включает ffprobe, используем ffmpeg
    cmd = [
        FFMPEG_PATH,
        "-i",
        str(audio_path),
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="ignore"
    )
    # Парсим stderr для длительности
    for line in result.stderr.split("\n"):
        if "Duration:" in line:
            # "Duration: 00:00:12.34, start: ..."
            parts = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = parts.split(":")
            return float(h) * 3600 + float(m) * 60 + float(s)
    return 8.0  # default


def create_video_clip(
    step_name: str, image_path: Path, audio_path: Path, output_path: Path
):
    """Создаёт клип (видео + аудио) через ffmpeg."""
    duration = get_audio_duration(audio_path) + 1.5  # пауза после озвучки

    cmd = [
        FFMPEG_PATH,
        "-y",
        "-loop",
        "1",
        "-i",
        str(image_path),
        "-i",
        str(audio_path),
        "-c:v",
        "libx264",
        "-tune",
        "stillimage",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-pix_fmt",
        "yuv420p",
        "-vf",
        f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=decrease,pad={VIDEO_WIDTH}:{VIDEO_HEIGHT}:(ow-iw)/2:(oh-ih)/2",
        "-t",
        str(duration),
        "-shortest",
        "-r",
        str(FPS),
        str(output_path),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )

    if result.returncode != 0:
        print(f"   ⚠️  Ошибка ffmpeg для {step_name}:")
        print(f"      {result.stderr[-500:]}")
        return False

    print(f"   🎬 Клип: {step_name} ({duration:.1f}s)")
    return True


def concatenate_clips():
    """Собирает финальное видео через concat demuxer."""
    print("\n🔗 Собираю финальное видео...")

    # Создаём список файлов для concat
    concat_list = OUTPUT_DIR / "concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for step in DEMO_STEPS:
            clip_path = CLIPS_DIR / f"{step['name']}.mp4"
            if clip_path.exists():
                # В concat demuxer пути должны быть с file '...'
                # Для Windows используем абсолютный путь с экранированием
                abs_path = str(clip_path.absolute()).replace("\\", "/")
                f.write(f"file '{abs_path}'\n")

    # Проверяем, что список не пустой
    if concat_list.stat().st_size == 0:
        print("❌ Нет клипов для объединения!")
        return False

    # FFmpeg concat demuxer
    cmd = [
        FFMPEG_PATH,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_list),
        "-c",
        "copy",
        str(FINAL_VIDEO),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
    )

    if result.returncode != 0:
        print("❌ Ошибка при объединении:")
        print(result.stderr[-1000:])
        return False

    size_mb = FINAL_VIDEO.stat().st_size / (1024 * 1024)
    print(f"✅ Финальное видео: {FINAL_VIDEO.name} ({size_mb:.1f} MB)")
    return True


async def main():
    print("=" * 60)
    print("🎬 SpectechPlatform — Автоматическое демо-видео")
    print("=" * 60)
    print(f"\n📂 Выход: {OUTPUT_DIR}")
    print(f"🗣️  Голос: {VOICE}")
    print(f"📐 Разрешение: {VIDEO_WIDTH}x{VIDEO_HEIGHT}")
    print(f"🎬 Шагов: {len(DEMO_STEPS)}")
    print(f"🔧 FFmpeg: {FFMPEG_PATH}")

    ensure_dirs()

    # Шаг 1: Скриншоты (включая title через Pillow)
    await take_screenshots()

    # Шаг 2: Озвучка
    await generate_all_voiceovers()

    # Шаг 3: Создаём клипы (видео + аудио для каждого шага)
    print("\n🎞️  Создаю клипы...")
    success_count = 0
    for step in DEMO_STEPS:
        image_path = SCREENSHOTS_DIR / f"{step['name']}.png"
        audio_path = AUDIO_DIR / f"{step['name']}.mp3"
        clip_path = CLIPS_DIR / f"{step['name']}.mp4"

        if not image_path.exists():
            print(f"   ⚠️  Пропуск {step['name']}: нет изображения")
            continue
        if not audio_path.exists():
            print(f"   ⚠️  Пропуск {step['name']}: нет аудио")
            continue

        if create_video_clip(step["name"], image_path, audio_path, clip_path):
            success_count += 1

    if success_count == 0:
        print("❌ Не создано ни одного клипа!")
        return

    # Шаг 4: Объединяем все клипы
    if concatenate_clips():
        print("\n" + "=" * 60)
        print("🎉 ГОТОВО!")
        print("=" * 60)
        print(f"\n📹 Видео: {FINAL_VIDEO}")

        # Получаем длительность финального видео
        duration = get_audio_duration(FINAL_VIDEO)
        print(f"⏱️  Длительность: {duration:.1f} сек ({duration/60:.1f} мин)")
        print(f"📊 Размер: {FINAL_VIDEO.stat().st_size / (1024*1024):.1f} MB")
        print("\n📝 Следующие шаги:")
        print("   1. Откройте видео и проверьте качество")
        print("   2. Загрузите на YouTube: spectehpro")
    else:
        print("❌ Не удалось создать финальное видео")


if __name__ == "__main__":
    asyncio.run(main())
