# =============================================================================
# SpectechPlatform Environment Variables
# =============================================================================
# Скопируйте этот файл в .env и измените значения для вашего окружения
# cp .env.example .env

# =============================================================================
# DATABASE (PostgreSQL)
# =============================================================================
POSTGRES_USER=spectech
POSTGRES_PASSWORD=change-this-secure-password # pragma: allowlist secret
POSTGRES_DB=spectech

# =============================================================================
# REDIS
# =============================================================================
# Redis используется для кэширования и очередей задач

# =============================================================================
# MINIO (S3-совместимое хранилище)
# =============================================================================
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=change-this-minio-password  # pragma: allowlist secret

# =============================================================================
# JWT AUTHENTICATION
# =============================================================================
# ВАЖНО: Сгенерируйте безопасный секретный ключ для production!
# Генерация: python -c "import secrets; print(secrets.token_urlsafe(64))"
JWT_SECRET_KEY=change-this-to-secure-random-string-in-production  # pragma: allowlist secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# =============================================================================
# APPLICATION
# =============================================================================
APP_NAME=SpectechPlatform
APP_VERSION=0.1.0
ENVIRONMENT=production
DEBUG=false

# =============================================================================
# CORS (Cross-Origin Resource Sharing)
# =============================================================================
# Укажите все домены, с которых разрешены запросы (через запятую)
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,https://your-domain.com

# =============================================================================
# FRONTEND
# =============================================================================
VITE_API_URL=http://localhost:8000/api/v1
VITE_WS_URL=ws://localhost:8000/api/v1/ws

# =============================================================================
# SENTRY (Error Tracking) - опционально
# =============================================================================
# SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id

# =============================================================================
# EMAIL (SMTP) - для отправки уведомлений
# =============================================================================
# Используем Mailhog (локальный SMTP) - не требует регистрации!
# Web UI: http://localhost:8025
EMAIL_ENABLED=true
SMTP_HOST=mailhog
SMTP_PORT=1025
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=noreply@spectech.pro
SMTP_FROM_NAME=СпецТехника Про
SMTP_USE_TLS=false

# Frontend URL для ссылок в письмах
FRONTEND_URL=http://localhost:8080
