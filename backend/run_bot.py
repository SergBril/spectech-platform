"""Запуск Telegram бота СпецТехника.

Использование:
    python run_bot.py

Требования:
    - Переменная окружения TELEGRAM_BOT_TOKEN
    - PostgreSQL доступен
"""

import logging
import sys

from app.core.config import settings
from app.services.telegram_bot import telegram_bot_service

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("spectech.bot_runner")


def main():
    """Точка входа для запуска бота."""
    # Проверка токена
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning(
            "⚠️ TELEGRAM_BOT_TOKEN not set. Bot will not start.\n"
            "   1. Создайте бота через @BotFather в Telegram\n"
            "   2. Добавьте TELEGRAM_BOT_TOKEN=xxx в .env\n"
            "   3. Перезапустите run_bot.py"
        )
        sys.exit(0)
    
    logger.info("🤖 Starting Spectech Telegram Bot...")
    logger.info(f"📡 Telegram API: https://api.telegram.org")
    logger.info("⚠️  Note: В РФ может потребоваться VPN/прокси")
    
    try:
        telegram_bot_service.run_bot()
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        error_name = type(e).__name__
        logger.error(
            f"❌ Bot failed to start: {error_name}: {e}\n"
            f"   Возможные причины:\n"
            f"   - Telegram API заблокирован (в РФ нужен VPN)\n"
            f"   - Невалидный TELEGRAM_BOT_TOKEN\n"
            f"   - Проблемы с сетью"
        )
        # Не падаем — приложение продолжает работать без бота
        sys.exit(1)


if __name__ == "__main__":
    main()