from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = (
        "postgresql+psycopg://spectech:spectech_dev_password@localhost:5432/spectech"
    )
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30
    app_name: str = "SpectechPlatform"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"
    storage_provider: str = "local"
    local_storage_dir: str = "./storage"
    rate_limit_enabled: bool = False
    frontend_url: str = "http://localhost:3000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
