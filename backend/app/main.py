import logging

from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import files, tasks
from app.api.routes import websocket as ws_routes
from app.core.db import Base, engine
from app.core.exception_handlers import (
    general_exception_handler,
    sqlalchemy_exception_handler,
    validation_exception_handler,
)
from app.core.logging_config import setup_logging
from app.models import *  # noqa: F401, F403 — импортирует ВСЕ модели

# Настраиваем логирование
setup_logging("INFO")
logger = logging.getLogger("spectech.app")
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    acts,
    auth,
    categories,
    contractors,
    invoices,
    me,
    payments,
    payouts,
    rbac,
    requests,
    shifts,
    system,
    telematics,
    vehicles,
)
from app.core.config import settings
from app.core.middleware import RequestLoggingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"🚀 {settings.app_name} v{settings.app_version} starting...")
    yield
    print("👋 Shutting down...")
    # Создаём таблицы если их нет


from app.models import *  # noqa: F401, F403 — импортируем все модели

Base.metadata.create_all(bind=engine)


# 1. Создаём приложение
app = FastAPI(
    title="SpectechPlatform",
    version="0.5.0-dev",
    description="Платформа управления спецтехникой",
)
# Создаём все таблицы в БД при старте (для dev-режима)
# В production использовать Alembic миграции
Base.metadata.create_all(bind=engine)
# Регистрируем обработчики ошибок
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)
# 2. CORS middleware (если есть)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Наш middleware логирования (ПОСЛЕДНИМ!)

app.add_middleware(RequestLoggingMiddleware)

# 4. Роутеры
# Auth
app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])

# Catalog
app.include_router(categories.router, prefix="/api/v1/categories", tags=["catalog"])
app.include_router(vehicles.router, prefix="/api/v1/vehicles", tags=["catalog"])

# Dispatch
app.include_router(requests.router, prefix="/api/v1/requests", tags=["dispatch"])
app.include_router(shifts.router, prefix="/api/v1/shifts", tags=["dispatch"])

# Contractors
app.include_router(
    contractors.router, prefix="/api/v1/contractors", tags=["contractors"]
)

# RBAC
app.include_router(rbac.router, prefix="/api/v1/rbac", tags=["rbac"])
app.include_router(me.router, prefix="/api/v1/me", tags=["me"])

# Finance
app.include_router(invoices.router, prefix="/api/v1/invoices", tags=["finance"])
app.include_router(acts.router, prefix="/api/v1/acts", tags=["finance"])
app.include_router(payouts.router, prefix="/api/v1/payouts", tags=["finance"])
app.include_router(payments.router, prefix="/api/v1/payments", tags=["finance"])

# Telematics
app.include_router(telematics.router, prefix="/api/v1/telematics", tags=["telematics"])

# Tasks (Celery)
app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["tasks"])

# System (новый из Дня 1 Недели 4)
app.include_router(system.router, prefix="/api/v1/system", tags=["system"])
# Files (storage)
app.include_router(files.router, prefix="/api/v1/files", tags=["files"])
# WebSocket
app.include_router(ws_routes.router, prefix="/api/v1", tags=["websocket"])
1

allowed_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {"status": "healthy", "version": settings.app_version}


@app.get("/ready")
def readiness_check():
    from sqlalchemy import text

    from app.core.db import SessionLocal

    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_ok = True
    except Exception:
        db_ok = False

    return {"status": "ready" if db_ok else "not_ready", "checks": {"database": db_ok}}
