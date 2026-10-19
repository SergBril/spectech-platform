"""Конфигурация приложения через pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения из .env файла."""

    # App
    app_name: str = "SpectechPlatform"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"
    environment: str = "development"
    TESTING: bool = False

    # Database
    database_url: str = (
        "postgresql+psycopg://spectech:spectech_dev_password@localhost:5432/spectech?sslmode=disable"
    )

    # Diadoc (EDO)
    DIADOC_API_KEY: str = ""
    DIADOC_BOX_ID: str = ""
    DIADOC_USE_SANDBOX: bool = True

    # Redis settings
    redis_host: str = "redis"
    redis_port_number: int = Field(default=6379, alias="REDIS_PORT_NUMBER")
    redis_db: int = 0
    redis_password: str = ""

    @property
    def redis_url(self) -> str:
        """URL для подключения к Redis."""
        return f"redis://{self.redis_host}:{self.redis_port_number}/{self.redis_db}"

    # JWT Settings
    jwt_secret_key: str = Field(
        default="CHANGE-ME-IN-PRODUCTION-use-openssl-rand-hex-32",
        alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=1440, alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    refresh_token_expire_days: int = Field(
        default=30, alias="REFRESH_TOKEN_EXPIRE_DAYS"
    )

    # CORS
    cors_origins: str = "http://localhost:3000"
    frontend_url: str = "http://localhost:3000"

    # Storage
    storage_provider: str = "local"
    local_storage_dir: str = "./storage"

    # Rate limiting
    rate_limit_enabled: bool = False

    # Email (SMTP)
    SMTP_HOST: str = Field(default="smtp.yandex.ru", description="SMTP server host")
    SMTP_PORT: int = Field(default=465, description="SMTP server port")
    SMTP_USER: str = Field(default="", description="SMTP username")
    SMTP_PASSWORD: str = Field(default="", description="SMTP password")
    SMTP_FROM_EMAIL: str = Field(
        default="noreply@spectech.dev", description="From email"
    )
    SMTP_FROM_NAME: str = Field(default="СпецТехника Про", description="From name")
    SMTP_USE_TLS: bool = Field(default=True, description="Use TLS/SSL")
    EMAIL_ENABLED: bool = Field(default=True, alias="EMAIL_ENABLED")

    # Application URLs
    FRONTEND_URL: str = Field(default="http://localhost:8080", alias="FRONTEND_URL")

    # MinIO (S3) Storage Settings
    MINIO_ENDPOINT: str = "http://localhost:9000"
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "minioadmin"
    MINIO_BUCKET: str = "spectech-docs"

    # Sentry
    sentry_dsn: str | None = None

    # Platform Owner Access
    PLATFORM_OWNER_EMAIL: str = Field(
        default="",
        alias="PLATFORM_OWNER_EMAIL",
        description="Email of platform owner with admin access",
    )

    # === Telegram Notifications (опционально) ===

    TELEGRAM_PROXY_URL: str = Field(
        default="",
        description="Прокси для Telegram API (socks5://user:pass@host:port или http://...)",
    )

    TELEGRAM_ENABLED: bool = Field(
        default=False,
        description="Включить Telegram уведомления (может не работать в РФ без прокси)",
    )
    TELEGRAM_BOT_TOKEN: str = Field(
        default="",
        description="Токен Telegram бота (получить у @BotFather)",
    )
    TELEGRAM_DEFAULT_CHAT_ID: str = Field(
        default="",
        description="Chat ID для системных уведомлений (эскалации споров)",
    )
    TELEGRAM_TIMEOUT_SECONDS: int = Field(
        default=5,
        description="Таймаут отправки (если Telegram заблокирован — быстро упадём)",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # === Background Tasks ===
    SCHEDULER_ENABLED: bool = Field(
        default=True,
        description="Включить планировщик фоновых задач",
    )
    SCHEDULER_INTERVAL_MINUTES: int = Field(
        default=5,
        description="Интервал проверки просроченных споров (минуты)",
    )


settings = Settings()
