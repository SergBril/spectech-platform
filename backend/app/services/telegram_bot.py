"""Telegram Bot для управления платформой СпецТехника."""
    
import logging
import os
from datetime import datetime, date, timedelta
from decimal import Decimal

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.auth import User
from app.models.catalog import Vehicle
from app.models.rental import Rental, RentalStatus
from app.models.dispatch import Request, RequestStatus
from app.models.marketplace import MarketplaceOffer

logger = logging.getLogger("spectech.telegram_bot")

# Состояния для ConversationHandler
LINK_ACCOUNT, AWAITING_CODE = range(2)


class TelegramBotService:
    """Сервис Telegram бота."""

    def __init__(self):
        self.application = None

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start — приветствие."""
        user = update.effective_user
        
        # Проверяем, привязан ли аккаунт
        db = SessionLocal()
        try:
            linked_user = self._find_user_by_telegram(db, user.id)
            
            if linked_user:
                keyboard = [
                    [
                        InlineKeyboardButton("🚜 Мои аренды", callback_data="my_rentals"),
                        InlineKeyboardButton("🚛 Моя техника", callback_data="my_vehicles"),
                    ],
                    [
                        InlineKeyboardButton("📋 Новые заявки", callback_data="new_requests"),
                        InlineKeyboardButton("📊 Статистика", callback_data="stats"),
                    ],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"👋 Добро пожаловать, {linked_user.full_name or user.first_name}!\n\n"
                    f"Ваш аккаунт привязан к платформе.\n\n"
                    f"Выберите действие:",
                    reply_markup=reply_markup,
                )
            else:
                await update.message.reply_text(
                    f"👋 Здравствуйте, {user.first_name}!\n\n"
                    f"Ваш Telegram аккаунт ещё не привязан к платформе.\n\n"
                    f"Чтобы привязать, используйте команду /link_account"
                )
        finally:
            db.close()

    async def link_account(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /link_account — привязка Telegram к аккаунту."""
        await update.message.reply_text(
            "🔗 <b>Привязка аккаунта</b>\n\n"
            "Чтобы привязать ваш Telegram к аккаунту платформы, "
            "отправьте код привязки.\n\n"
            "Код можно получить в личном кабинете на сайте:\n"
            "Настройки → Telegram → Получить код\n\n"
            "Или отправьте /cancel для отмены.",
            parse_mode="HTML",
        )
        return AWAITING_CODE

    async def handle_link_code(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка кода привязки."""
        code = update.message.text.strip()
        telegram_id = update.effective_user.id
        
        db = SessionLocal()
        try:
            # Ищем пользователя с этим кодом
            user = (
                db.query(User)
                .filter(User.telegram_link_code == code)
                .first()
            )
            
            if not user:
                await update.message.reply_text(
                    "❌ Неверный код привязки.\n\n"
                    "Попробуйте ещё раз или используйте /cancel для отмены."
                )
                return AWAITING_CODE
            
            # Привязываем Telegram
            user.telegram_id = telegram_id
            user.telegram_link_code = None
            db.commit()
            
            await update.message.reply_text(
                f"✅ <b>Аккаунт успешно привязан!</b>\n\n"
                f"Теперь вы можете управлять платформой через Telegram.\n\n"
                f"Используйте /start для начала работы.",
                parse_mode="HTML",
            )
            
            logger.info(f"User {user.id} linked Telegram {telegram_id}")
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"Error linking account: {e}", exc_info=True)
            await update.message.reply_text(
                "❌ Ошибка при привязке аккаунта. Попробуйте позже."
            )
            return ConversationHandler.END
        finally:
            db.close()

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена текущей операции."""
        await update.message.reply_text("❌ Операция отменена.")
        return ConversationHandler.END

    async def my_rentals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Мои аренды."""
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        db = SessionLocal()
        try:
            user = self._find_user_by_telegram(db, telegram_id)
            if not user:
                await query.edit_message_text("❌ Аккаунт не привязан. Используйте /link_account")
                return
            
            # Получаем активные аренды
            rentals = (
                db.query(Rental)
                .filter(
                    Rental.company_id == user.company_id,
                    Rental.status.in_([RentalStatus.ACTIVE, RentalStatus.OVERDUE]),
                )
                .order_by(Rental.start_date.desc())
                .limit(10)
                .all()
            )
            
            if not rentals:
                await query.edit_message_text(
                    "📋 <b>Мои аренды</b>\n\n"
                    "У вас нет активных аренд.",
                    parse_mode="HTML",
                )
                return
            
            message = "📋 <b>Активные аренды:</b>\n\n"
            for rental in rentals:
                status_emoji = "🟢" if rental.status == RentalStatus.ACTIVE else "🔴"
                message += (
                    f"{status_emoji} <b>#{rental.id}</b>\n"
                    f"   Начало: {rental.start_date.strftime('%d.%m.%Y')}\n"
                    f"   Окончание: {rental.end_date.strftime('%d.%m.%Y')}\n"
                    f"   Сумма: {rental.total_amount:.0f} ₽\n\n"
                )
            
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="start_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message, parse_mode="HTML", reply_markup=reply_markup)
            
        finally:
            db.close()

    async def my_vehicles(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Моя техника."""
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        db = SessionLocal()
        try:
            user = self._find_user_by_telegram(db, telegram_id)
            if not user:
                await query.edit_message_text("❌ Аккаунт не привязан. Используйте /link_account")
                return
            
            # Получаем технику компании
            vehicles = (
                db.query(Vehicle)
                .filter(
                    Vehicle.company_id == user.company_id,
                    Vehicle.is_deleted == False,
                )
                .order_by(Vehicle.name)
                .limit(10)
                .all()
            )
            
            if not vehicles:
                await query.edit_message_text(
                    "🚛 <b>Моя техника</b>\n\n"
                    "У вас нет техники в системе.",
                    parse_mode="HTML",
                )
                return
            
            message = "🚛 <b>Ваша техника:</b>\n\n"
            for vehicle in vehicles:
                status_emoji = "🟢" if vehicle.status == "free" else "🔴"
                marketplace_badge = "📢" if vehicle.is_available_for_rent else ""
                
                message += (
                    f"{status_emoji} <b>{vehicle.name}</b> {marketplace_badge}\n"
                    f"   Статус: {vehicle.status}\n"
                )
                
                if vehicle.hourly_rate:
                    message += f"   Ставка: {vehicle.hourly_rate:.0f} ₽/час\n"
                
                message += "\n"
            
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="start_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message, parse_mode="HTML", reply_markup=reply_markup)
            
        finally:
            db.close()

    async def new_requests(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Новые заявки из Marketplace."""
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        db = SessionLocal()
        try:
            user = self._find_user_by_telegram(db, telegram_id)
            if not user:
                await query.edit_message_text("❌ Аккаунт не привязан. Используйте /link_account")
                return
            
            # Получаем новые заявки
            requests = (
                db.query(Request)
                .filter(
                    Request.company_id == user.company_id,
                    Request.status == RequestStatus.new,
                )
                .order_by(Request.created_at.desc())
                .limit(10)
                .all()
            )
            
            if not requests:
                await query.edit_message_text(
                    "📋 <b>Новые заявки</b>\n\n"
                    "Нет новых заявок.",
                    parse_mode="HTML",
                )
                return
            
            message = "📋 <b>Новые заявки:</b>\n\n"
            keyboard = []
            
            for req in requests:
                message += (
                    f"🆕 <b>#{req.id}</b> — {req.work_type}\n"
                    f"   {req.planned_start.strftime('%d.%m.%Y %H:%M')}\n"
                )
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ Принять #{req.id}",
                        callback_data=f"accept_request_{req.id}",
                    ),
                    InlineKeyboardButton(
                        f"❌ Отклонить #{req.id}",
                        callback_data=f"reject_request_{req.id}",
                    ),
                ])
            
            keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="start_menu")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message, parse_mode="HTML", reply_markup=reply_markup)
            
        finally:
            db.close()

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка callback от inline-кнопок."""
        query = update.callback_query
        data = query.data
        
        if data == "my_rentals":
            await self.my_rentals(update, context)
        elif data == "my_vehicles":
            await self.my_vehicles(update, context)
        elif data == "new_requests":
            await self.new_requests(update, context)
        elif data == "start_menu":
            await self.start(update, context)
        elif data.startswith("accept_request_"):
            request_id = int(data.split("_")[-1])
            await self._accept_request(update, request_id)
        elif data.startswith("reject_request_"):
            request_id = int(data.split("_")[-1])
            await self._reject_request(update, request_id)

    async def _accept_request(self, update: Update, request_id: int):
        """Принять заявку."""
        query = update.callback_query
        await query.answer("✅ Заявка принята")
        
        db = SessionLocal()
        try:
            request = db.get(Request, request_id)
            if request:
                request.status = RequestStatus.assigned
                db.commit()
                
                await query.edit_message_text(
                    f"✅ <b>Заявка #{request_id} принята</b>\n\n"
                    "Заявка переведена в статус 'assigned'.",
                    parse_mode="HTML",
                )
        finally:
            db.close()

    async def _reject_request(self, update: Update, request_id: int):
        """Отклонить заявку."""
        query = update.callback_query
        await query.answer("❌ Заявка отклонена")
        
        db = SessionLocal()
        try:
            request = db.get(Request, request_id)
            if request:
                request.status = RequestStatus.cancelled
                db.commit()
                
                await query.edit_message_text(
                    f"❌ <b>Заявка #{request_id} отклонена</b>",
                    parse_mode="HTML",
                )
        finally:
            db.close()

    def _find_user_by_telegram(self, db: Session, telegram_id: int) -> User | None:
        """Находит пользователя по Telegram ID."""
        return (
            db.query(User)
            .filter(User.telegram_id == telegram_id)
            .first()
        )

    def run_bot(self):
        """Запускает бота с поддержкой прокси для РФ."""
        if not settings.TELEGRAM_BOT_TOKEN:
            logger.warning("⚠️ TELEGRAM_BOT_TOKEN not set. Bot will not start.")
            return
        
        proxy_url = getattr(settings, "TELEGRAM_PROXY_URL", None) or os.getenv("TELEGRAM_PROXY_URL")
        
        builder = Application.builder().token(settings.TELEGRAM_BOT_TOKEN)
        
        if proxy_url:
            logger.info(f"🌐 Using proxy: {proxy_url.split('@')[-1]}")
            try:
                from telegram.request import HTTPXRequest
                
                # 🆕 ПРАВИЛЬНО для python-telegram-bot v22
                request = HTTPXRequest(
                    proxy=proxy_url,  # ← proxy, а не proxy_url
                    connect_timeout=10.0,
                    read_timeout=10.0,
                    write_timeout=10.0,
                    pool_timeout=10.0,
                )
                builder = builder.request(request)
            except Exception as e:
                logger.error(f"❌ Failed to setup proxy: {e}")
                return
        
        self.application = builder.build()
        
        # Conversation handler для /link_account
        conv_handler = ConversationHandler(
            entry_points=[CommandHandler("link_account", self.link_account)],
            states={
                AWAITING_CODE: [
                    MessageHandler(
                        filters.TEXT & ~filters.COMMAND,
                        self.handle_link_code,
                    )
                ],
            },
            fallbacks=[CommandHandler("cancel", self.cancel)],
        )
        
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(conv_handler)
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        logger.info("🤖 Telegram bot started")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)

# Singleton
telegram_bot_service = TelegramBotService()