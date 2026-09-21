"""
🎬 Прямая запись экрана + микрофон через Python (без OBS).

Использует:
- mss для захвата экрана
- sounddevice для записи микрофона
- ffmpeg для объединения в MP4

Запуск:
    python marketing/demo-videos/record_direct.py
"""

import asyncio
import subprocess
import threading
import time
import wave
from datetime import datetime
from pathlib import Path

import mss
import numpy as np
import sounddevice as sd

# === НАСТРОЙКИ ===
VIDEO_DIR = Path(r"C:\Users\osavi\Videos\SpectechDemo")
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
SCREEN_FILE = VIDEO_DIR / f"screen_{TIMESTAMP}.mp4"
AUDIO_FILE = VIDEO_DIR / f"audio_{TIMESTAMP}.wav"
FINAL_FILE = VIDEO_DIR / f"demo_{TIMESTAMP}.mp4"

FPS = 20
DURATION_SECONDS = 60  # Длительность записи

# Настройки аудио
SAMPLE_RATE = 44100
CHANNELS = 1


class ScreenRecorder:
    """Запись экрана через mss + ffmpeg."""

    def __init__(self, output_file, fps=20):
        self.output_file = output_file
        self.fps = fps
        self.recording = False
        self.thread = None

    def start(self):
        self.recording = True
        self.thread = threading.Thread(target=self._record)
        self.thread.start()

    def _record(self):
        with mss.mss() as sct:
            monitor = sct.monitors[1]  # Основной монитор

            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "rawvideo",
                "-vcodec",
                "rawvideo",
                "-s",
                f"{monitor['width']}x{monitor['height']}",
                "-pix_fmt",
                "bgra",
                "-r",
                str(self.fps),
                "-i",
                "-",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-preset",
                "ultrafast",
                "-crf",
                "23",
                str(self.output_file),
            ]

            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            try:
                while self.recording:
                    img = sct.grab(monitor)
                    process.stdin.write(img.rgb)
                    time.sleep(1 / self.fps)
            finally:
                if process.stdin:
                    process.stdin.close()
                process.wait()

    def stop(self):
        self.recording = False
        if self.thread:
            self.thread.join()


class AudioRecorder:
    """Запись микрофона через sounddevice."""

    def __init__(self, output_file, sample_rate=44100, channels=1):
        self.output_file = output_file
        self.sample_rate = sample_rate
        self.channels = channels
        self.recording = False
        self.thread = None
        self.frames = []

    def start(self):
        self.recording = True
        self.thread = threading.Thread(target=self._record)
        self.thread.start()

    def _record(self):
        def callback(indata, frames, time_info, status):
            if self.recording:
                self.frames.append(indata.copy())

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            callback=callback,
        ):
            while self.recording:
                time.sleep(0.1)

    def stop(self):
        self.recording = False
        if self.thread:
            self.thread.join()

        if self.frames:
            audio_data = np.concatenate(self.frames, axis=0)
            with wave.open(str(self.output_file), "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes((audio_data * 32767).astype(np.int16).tobytes())


async def show_demo_in_browser():
    """Показывает демо через curl-запросы в консоли."""
    import httpx

    base_url = "http://localhost:8000"

    print("\n🎬 ДЕМОНСТРАЦИЯ API:")
    print("=" * 60)

    # 1. Каталог компаний
    print("\n📋 [1/4] GET /api/v1/public/companies")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{base_url}/api/v1/public/companies")
        companies = resp.json()
        print(f"   Найдено компаний: {len(companies)}")
        for c in companies[:2]:
            print(f"   - {c['name']} (техники: {c['vehicles_count']})")

    await asyncio.sleep(10)

    # 2. Каталог техники
    print("\n🚜 [2/4] GET /api/v1/public/vehicles?available_only=true")
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{base_url}/api/v1/public/vehicles",
            params={"available_only": "true"},
        )
        vehicles = resp.json()
        print(f"   Доступно техники: {len(vehicles)}")
        for v in vehicles[:4]:
            print(
                f"   - {v['name']}: {v['hourly_rate']} руб/час "
                f"({v['owner_company_name']})"
            )

    await asyncio.sleep(10)

    # 3. Отклики на заявку
    print("\n💬 [3/4] GET /api/v1/marketplace/requests/7/offers")
    async with httpx.AsyncClient() as client:
        # Сначала получим токен
        login_resp = await client.post(
            f"{base_url}/api/v1/auth/login",
            json={"email": "admin@spectech.dev", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            f"{base_url}/api/v1/marketplace/requests/7/offers",
            headers={"Authorization": f"Bearer {token}"},
        )
        offers = resp.json()
        print(f"   Откликов на заявку #7: {len(offers)}")
        for o in offers:
            print(
                f"   - {o['owner_company_name']}: "
                f"{o['offered_price']} руб ({o['status']})"
            )

    await asyncio.sleep(10)

    # 4. Чат по заявке
    print("\n📨 [4/4] POST /api/v1/chat/requests/7/messages")
    async with httpx.AsyncClient() as client:
        login_resp = await client.post(
            f"{base_url}/api/v1/auth/login",
            json={"email": "admin@spectech.dev", "password": "admin123"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            f"{base_url}/api/v1/chat/requests/7/messages",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "content": "Привет! Это автоматическая запись демо 🎬",
                "message_type": "text",
            },
        )
        msg = resp.json()
        print(f"   Сообщение #{msg['id']} отправлено")
        print(f"   Текст: {msg['content']}")

    await asyncio.sleep(10)

    print("\n" + "=" * 60)
    print("✅ Демонстрация завершена")
    print("=" * 60)


def combine_audio_video(screen_file, audio_file, output_file):
    """Объединяет видео и аудио через ffmpeg."""
    print("\n🎞️  Объединяю видео и аудио...")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(screen_file),
        "-i",
        str(audio_file),
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        str(output_file),
    ]
    subprocess.run(cmd, capture_output=True)
    print(f"✅ Финальное видео: {output_file}")


def main():
    print("=" * 60)
    print("🎬 SpectechPlatform — Прямая запись демо")
    print("=" * 60)

    VIDEO_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n📂 Папка для видео: {VIDEO_DIR}")
    print(f"⏱️  Длительность: {DURATION_SECONDS} секунд")

    print("\n⚠️  ВАЖНО:")
    print("   1. Говорите в микрофон во время записи")
    print("   2. Не двигайте мышью слишком быстро")
    print("   3. Отключите уведомления Windows")

    print("\n⏳ Старт через 5 секунд... (Ctrl+C для отмены)")

    try:
        for i in range(5, 0, -1):
            print(f"   {i}...")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n❌ Отменено")
        return

    # Запускаем запись
    screen_recorder = ScreenRecorder(SCREEN_FILE, fps=FPS)
    audio_recorder = AudioRecorder(AUDIO_FILE)

    print("\n🎥 Начинаю запись экрана...")
    screen_recorder.start()

    print("🎤 Начинаю запись микрофона...")
    audio_recorder.start()

    try:
        # Выполняем демонстрацию
        asyncio.run(show_demo_in_browser())

        # Дополнительная пауза
        print("\n⏳ Финальная пауза 5 секунд...")
        time.sleep(5)

    except KeyboardInterrupt:
        print("\n⚠️  Прервано")
    finally:
        # Останавливаем запись
        print("\n⏹️  Останавливаю запись...")
        screen_recorder.stop()
        audio_recorder.stop()

    # Объединяем
    combine_audio_video(SCREEN_FILE, AUDIO_FILE, FINAL_FILE)

    # Показываем результат
    print("\n" + "=" * 60)
    print("🎉 ГОТОВО!")
    print("=" * 60)
    print(f"\n📹 Видео: {FINAL_FILE}")
    print(f"📊 Размер: {FINAL_FILE.stat().st_size / (1024*1024):.1f} MB")


if __name__ == "__main__":
    main()
