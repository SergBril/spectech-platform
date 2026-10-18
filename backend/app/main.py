"""Главный файл приложения FastAPI."""

from dotenv import load_dotenv

load_dotenv()  # Загружает backend/.env
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import (
    SQLAlchemyError,
)

from app.api.routes import (
    acts,
    admin,
    analytics,
    auth,
    bank_statements,
    benchmark,
    catalog,
    categories,
    chat,
    companies,
    contractors,
    debug,
    disputes,
    downtime,
    driver,
    drivers,
    email,
    email_bulk,
    email_templates,
    export,
    files,
    finance,
    gps,
    invoices,
    maintenance,
    marketplace,
    marketplace_listings,
    me,
    payments,
    payouts,
    public,  # 🆕 Маркетплейс
    rbac,
    rentals,
    requests,
    salaries,
    secure_test,
    shifts,
    signature,
    system,
    tasks,
    tax,
    telematics,
    vehicles,
)
from app.api.routes import (
    map as map_routes,
)
from app.api.routes import websocket as ws_routes
from app.core.config import settings
from app.core.exception_handlers import (
    general_exception_handler,
    sqlalchemy_exception_handler,
    validation_exception_handler,
)
from app.core.logging_config import setup_logging
from app.core.metrics import setup_metrics
from app.core.middleware import RequestLoggingMiddleware
from app.core.sentry_config import init_sentry
from app.models import *  # noqa: F401, F403
from app.services import storage_service
from app.tasks.scheduler import start_scheduler, stop_scheduler

# Настройка логирования
setup_logging("INFO")
logger = logging.getLogger("spectech.app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 SpectechPlatform v0.1.0 starting...")

    # Запускаем планировщик фоновых задач
    start_scheduler()

    # Пропускаем подключение к MinIO в тестовом режиме
    if not settings.TESTING:
        try:
            storage_service.ensure_bucket_exists()
            logger.info("✅ MinIO (S3) connection OK")
        except Exception as e:
            logger.warning(f"⚠️ MinIO connection failed: {e}")

    yield

    # Graceful shutdown sequence
    logger.info("🔄 Shutting down scheduler...")
    stop_scheduler()

    # Close DB connections
    try:
        from app.core.db import engine

        engine.dispose()
        logger.info("✅ Database connections closed")
    except Exception as e:
        logger.warning(f"⚠️ DB cleanup error: {e}")

    # Close Redis
    try:
        from app.core.redis import redis_client

        if redis_client:
            redis_client.close()
            logger.info("✅ Redis connection closed")
    except Exception:
        pass

    logger.info("👋 SpectechPlatform shut down gracefully")


# 1. Создание приложения
app = FastAPI(
    title="СпецТехника Про API",
    description="""
    # 🚜 Платформа управления спецтехникой

    Полнофункциональная система для управления парком спецтехники,
    учёта топлива, отслеживания GPS и управления заявками.

    ## Возможности

    * 🔐 **Аутентификация** — JWT токены, RBAC
    * 🚗 **Транспорт** — каталог, статусы, история
    * 📍 **GPS трекинг** — реальное время, геозоны
    * ⛽ **Топливо** — учёт заправок и сливов
    * 📋 **Заявки** — управление работами
    * 💰 **Финансы** — счета, акты, выплаты
    * 🔔 **Алерты** — уведомления в реальном времени
    """,
    version="1.0.0",
    terms_of_service="https://spectech.pro/terms",
    contact={
        "name": "СпецТехника Про",
        "url": "https://spectech.pro",
        "email": "support@spectech.pro",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_url="/api/v1/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

#

# Setup Prometheus metrics
if settings.environment != "testing":
    setup_metrics(app)

# Инициализируем Sentry
init_sentry()

# Add Prometheus metrics


# Добавляем Request ID middleware (ПЕРВЫМ!)
# app.add_middleware(RequestIDMiddleware)  # временно отключено

# Таблицы создаются через Alembic миграции при старте контейнера
print("✅ Database migrations managed by Alembic")

# 3. Регистрируем обработчики ошибок
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# 4. Middleware
allowed_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3001",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],  # ← ВАЖНО для скачивания файлов!
)

app.add_middleware(RequestLoggingMiddleware)

# 5. Роутеры API
# Debug endpoints

# Debug endpoints (без префикса - он уже в router)
app.include_router(debug.router, prefix="/api/v1", tags=["debug"])

app.include_router(auth.router, prefix="/api/v1", tags=["auth"])
app.include_router(categories.router, prefix="/api/v1/categories", tags=["catalog"])
app.include_router(
    vehicles.router, prefix="/api/v1", tags=["🚜 Vehicles (Спецтехника)"]
)
app.include_router(
    drivers.router, prefix="/api/v1/drivers", tags=["👷 Drivers (Водители)"]
)
app.include_router(requests.router, prefix="/api/v1/requests", tags=["dispatch"])
app.include_router(shifts.router, prefix="/api/v1/shifts", tags=["dispatch"])
app.include_router(
    contractors.router, prefix="/api/v1/contractors", tags=["contractors"]
)
app.include_router(email.router, prefix="/api/v1/email", tags=["email"])
app.include_router(rbac.router, prefix="/api/v1/rbac", tags=["rbac"])
app.include_router(me.router, prefix="/api/v1", tags=["me"])
app.include_router(invoices.router, prefix="/api/v1/invoices", tags=["finance"])
app.include_router(acts.router, prefix="/api/v1/acts", tags=["finance"])
app.include_router(payouts.router, prefix="/api/v1/finance/payouts", tags=["finance"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["finance"])
app.include_router(telematics.router, prefix="/api/v1/telematics", tags=["telematics"])
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])
app.include_router(system.router, prefix="/api/v1/system", tags=["system"])
app.include_router(files.router, prefix="/api/v1/files", tags=["files"])
app.include_router(ws_routes.router, prefix="/api/v1", tags=["websocket"])
app.include_router(benchmark.router, prefix="/api/v1", tags=["benchmark"])
app.include_router(secure_test.router, prefix="/api/v1", tags=["🔒 Secure Test (RBAC)"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(export.router, prefix="/api/v1/export", tags=["export"])
app.include_router(tax.router, prefix="/api/v1", tags=["📊 Tax & VAT (НДС)"])
app.include_router(companies.router, prefix="/api/v1", tags=["companies"])
app.include_router(
    marketplace.router, prefix="/api/v1", tags=["🎯 Marketplace (Отклики на заявки)"]
)
app.include_router(
    marketplace_listings.router,
    prefix="/api/v1",
    tags=["🛒 Marketplace (Управление объявлениями)"],
)
app.include_router(chat.router, prefix="/api/v1", tags=["💬 Chat (Чат по заявке)"])
app.include_router(public.router, prefix="/api/v1", tags=["🌐 Public (Маркетплейс)"])
app.include_router(
    maintenance.router, prefix="/api/v1", tags=["🔧 Maintenance (ТО и Ремонты)"]
)
app.include_router(email_templates.router, prefix="/api/v1")
app.include_router(email_bulk.router, prefix="/api/v1")
app.include_router(catalog.router, prefix="/api/v1")
app.include_router(signature.router, prefix="/api/v1/signature", tags=["signature"])
app.include_router(finance.router, prefix="/api/v1/finance", tags=["Финансы"])
app.include_router(disputes.router, prefix="/api/v1/disputes", tags=["disputes"])
app.include_router(downtime.router, prefix="/api/v1/downtime", tags=["downtime"])
app.include_router(rentals.router, prefix="/api/v1", tags=["📋 Rentals (Аренда)"])
app.include_router(
    bank_statements.router,
    prefix="/api/v1/banking",
    tags=["💳 Banking (Банковские выписки)"],
)
app.include_router(
    salaries.router, prefix="/api/v1/salaries", tags=["💰 Salaries (Зарплаты)"]
)
app.include_router(
    map_routes.router, prefix="/api/v1/map", tags=["🗺️ Map (Карта техники)"]
)
app.include_router(gps.router, prefix="/api/v1/gps", tags=["📡 GPS"])
app.include_router(
    driver.router, prefix="/api/v1/driver", tags=["📱 Driver (Мобильное приложение)"]
)
app.include_router(
    admin.router, prefix="/api/v1/admin", tags=["🔧 Admin (Админ-панель)"]
)
# app.include_router(reviews.router, prefix="/api/v1", tags=["⭐ Reviews (Отзывы и рейтинги)"])

uploads_dir = Path("uploads")
uploads_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="uploads"), name="static")


# 6. Кастомизация OpenAPI
def custom_openapi():
    """Custom OpenAPI schema."""
    # if app.openapi_schema:
    #     return app.openapi_schema
    app.openapi_schema = None  # Сбрасываем кэш
    openapi_schema = get_openapi(
        title="СпецТехника Про API",
        version="1.0.0",
        description=app.description,
        routes=app.routes,
    )
    openapi_schema["servers"] = [
        {"url": "http://localhost:8000", "description": "Development server"},
        {"url": "https://api.spectech.pro", "description": "Production server"},
    ]
    openapi_schema["tags"] = [
        {"name": "auth", "description": "Аутентификация и авторизация"},
        {"name": "catalog", "description": "Каталог транспорта"},
        {"name": "telematics", "description": "GPS трекинг и телематика"},
        {"name": "finance", "description": "Финансовые операции"},
        {"name": "dispatch", "description": "Заявки и смены"},
        {"name": "system", "description": "Системные endpoints"},
    ]
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# 7. Документация: главная страница
@app.get("/", include_in_schema=False, response_class=HTMLResponse)
async def root_landing():
    """Главная страница документации."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>СпецТехника Про API</title>
        <meta charset="utf-8">
        <style>
            body { font-family: -apple-system, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; background: #f5f5f5; }
            .container { background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }
            h2 { color: #34495e; }
            .card { background: #ecf0f1; padding: 20px; margin: 15px 0; border-radius: 8px; border-left: 4px solid #3498db; }
            a { display: inline-block; background: #3498db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 10px 10px 10px 0; }
            a:hover { background: #2980b9; }
            code { background: #2c3e50; color: #ecf0f1; padding: 2px 6px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚜 СпецТехника Про API</h1>
            <p><strong>Версия:</strong> 1.0.0 | <strong>Статус:</strong> Production</p>

            <h2>📚 Документация</h2>
            <div class="card">
                <a href="/docs">🔵 Swagger UI</a>
                <a href="/redoc">🔴 ReDoc</a>
                <a href="/api/v1/openapi.json">📄 OpenAPI JSON</a>
            </div>

            <h2>🚀 Быстрый старт</h2>
            <div class="card">
                <h3>1. Аутентификация</h3>
                <pre><code>POST /api/v1/auth/login
{
  "email": "admin@spectech.dev",
  "password": "admin123"
}</code></pre>
            </div>

            <h2>📋 Основные модули</h2>
            <ul>
                <li><strong>auth</strong> — аутентификация, JWT</li>
                <li><strong>catalog</strong> — каталог транспорта</li>
                <li><strong>telematics</strong> — GPS, алерты, геозоны</li>
                <li><strong>finance</strong> — счета, акты, выплаты</li>
                <li><strong>dispatch</strong> — заявки на работы</li>
            </ul>

            <h2>🔧 Среда</h2>
            <p>Base URL: <code>http://localhost:8000</code></p>
            <p>WebSocket: <code>ws://localhost:8000/ws</code></p>
        </div>
    </body>
    </html>
    """


# 10. Health check endpoints
@app.get("/health", tags=["system"])
def health_check():
    """Проверка здоровья сервиса."""
    return {"status": "healthy", "version": settings.app_version}


@app.get("/ready", tags=["system"])
def readiness_check():
    """Проверка готовности (БД)."""
    from sqlalchemy import text

    from app.core.db import SessionLocal

    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ready" if db_ok else "not_ready",
        "checks": {"database": db_ok},
    }


@app.get("/api/v1/debug/simple")
async def simple_debug():
    """Simple debug endpoint without router."""
    return {"message": "Simple debug works", "status": "ok"}
