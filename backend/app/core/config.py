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

    # Database
    database_url: str = (
        "postgresql+psycopg://spectech:spectech_dev_password@localhost:5432/spectech"
    )

    # Redis settings
    redis_host: str = "redis"
    redis_port_number: int = Field(
        default=6379, alias="REDIS_PORT_NUMBER"
    )  # ✅ НЕ конфликтует с K8s
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        """URL для подключения к Redis."""
        return f"redis://{self.redis_host}:{self.redis_port_number}/{self.redis_db}"

    redis_password: str = ""

    # JWT Settings
    jwt_secret_key: str = Field(
        default="CHANGE-ME-IN-PRODUCTION-use-openssl-rand-hex-32",
        alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(
        default=60 * 24, alias="ACCESS_TOKEN_EXPIRE_MINUTES"
    )  # 24 часа
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
    SMTP_HOST: str = Field(default="mailhog", alias="SMTP_HOST")
    SMTP_PORT: int = Field(default=1025, alias="SMTP_PORT")
    SMTP_USER: str = Field(default="", alias="SMTP_USER")
    SMTP_PASSWORD: str = Field(default="", alias="SMTP_PASSWORD")
    SMTP_FROM_EMAIL: str = Field(
        default="noreply@spectech.pro", alias="SMTP_FROM_EMAIL"
    )
    SMTP_FROM_NAME: str = Field(default="СпецТехника Про", alias="SMTP_FROM_NAME")
    SMTP_USE_TLS: bool = Field(default=False, alias="SMTP_USE_TLS")
    EMAIL_ENABLED: bool = Field(default=True, alias="EMAIL_ENABLED")

    # Application URLs
    FRONTEND_URL: str = Field(default="http://localhost:8080", alias="FRONTEND_URL")

    # ═══════════════════════════════════════════════════════════
    # MinIO (S3) Storage Settings
    # ═══════════════════════════════════════════════════════════
    MINIO_ENDPOINT: str = "http://minio:9000"  # Внутри Docker-сети
    MINIO_ROOT_USER: str = "minioadmin"  # Должно совпадать с docker-compose
    MINIO_ROOT_PASSWORD: str = "minioadmin"  # Должно совпадать с docker-compose
    MINIO_BUCKET: str = "spectech-docs"

    # SMTP настройки
    SMTP_HOST: str = Field(default="smtp.yandex.ru", description="SMTP server host")
    SMTP_PORT: int = Field(default=465, description="SMTP server port")
    SMTP_USER: str = Field(default="", description="SMTP username")
    SMTP_PASSWORD: str = Field(default="", description="SMTP password")
    SMTP_FROM_EMAIL: str = Field(
        default="noreply@spectech.dev", description="From email"
    )
    SMTP_FROM_NAME: str = Field(default="СпецТехника Про", description="From name")
    SMTP_USE_TLS: bool = Field(default=True, description="Use TLS/SSL")

    # Sentry
    sentry_dsn: str | None = None
    environment: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Игнорируем неизвестные поля из .env
    )


settings = Settings()
