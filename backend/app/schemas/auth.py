"""Схемы аутентификации и пользователей."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserLogin(BaseModel):
    """Схема входа в систему."""

    email: EmailStr = Field(
        ...,
        description="Email пользователя",
        examples=["admin@spectech.dev"],
    )
    password: str = Field(
        ...,
        min_length=6,
        description="Пароль (минимум 6 символов)",
        examples=["admin123"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "admin@spectech.dev",
                "password": "admin123",
            }
        }
    )


class UserRegister(BaseModel):
    """Схема регистрации нового пользователя."""

    email: EmailStr = Field(
        ...,
        description="Email пользователя",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=6,
        description="Пароль (минимум 6 символов)",
        examples=["securepass123"],
    )
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Полное имя пользователя",
        examples=["Иван Иванов"],
    )
    phone: str | None = Field(
        None,
        description="Номер телефона",
        examples=["+7 (999) 123-45-67"],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "user@example.com",
                "password": "securepass123",
                "full_name": "Иван Иванов",
                "phone": "+7 (999) 123-45-67",
            }
        }
    )


class Token(BaseModel):
    """Ответ с токенами (старая схема для совместимости)."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Тип токена")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIs...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
                "token_type": "bearer",
            }
        }
    )


class TokenResponse(BaseModel):
    """Ответ с токенами (новая схема)."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Тип токена")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIs...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
                "token_type": "bearer",
            }
        }
    )


class UserRead(BaseModel):
    """Схема чтения данных пользователя."""

    id: int = Field(..., description="ID пользователя", examples=[1])
    email: str = Field(..., description="Email", examples=["admin@spectech.dev"])
    full_name: str = Field(..., description="Полное имя", examples=["Admin User"])
    phone: str | None = Field(None, description="Телефон")
    company_id: int | None = Field(None, description="ID компании")
    is_superuser: bool = Field(..., description="Суперпользователь", examples=[False])
    created_at: datetime = Field(..., description="Дата создания")

    model_config = ConfigDict(from_attributes=True)
