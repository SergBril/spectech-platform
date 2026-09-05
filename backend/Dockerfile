# ═══════════════════════════════════════════════════════════════
# STAGE 1: Builder - установка зависимостей
# ═══════════════════════════════════════════════════════════════
FROM python:3.12-slim AS builder

WORKDIR /build

# Устанавливаем системные зависимости для СБОРКИ (не попадут в финальный образ)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем только requirements.txt (кэширование слоёв)
COPY requirements.txt .

# Устанавливаем Python зависимости в изолированную папку
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ═══════════════════════════════════════════════════════════════
# STAGE 2: Runtime - минимальный production образ
# ═══════════════════════════════════════════════════════════════
FROM python:3.12-slim AS runtime

WORKDIR /app

# Устанавливаем ТОЛЬКО runtime зависимости (без gcc!)
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    curl \
    fonts-dejavu-core \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd -r spectech \
    && useradd -r -g spectech -d /app -s /sbin/nologin spectech

# Копируем установленные зависимости из builder stage
COPY --from=builder /install /usr/local

# Копируем код приложения
COPY --chown=spectech:spectech . .

# Создаём папку для загрузок
RUN mkdir -p /app/uploads /app/logs \
    && chown -R spectech:spectech /app

# Health check - Docker будет проверять что приложение живо
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/system/health || exit 1

# Переключаемся на non-root пользователя (БЕЗОПАСНОСТЬ!)
USER spectech

# Открываем порт
EXPOSE 8000

# Production settings: 4 workers, graceful timeout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Запуск через uvicorn с 4 workers для production
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--log-level", "info", \
     "--access-log"]
