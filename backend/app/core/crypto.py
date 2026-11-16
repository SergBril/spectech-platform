"""Шифрование секретов интеграций в БД.

API-ключ Diadoc и токен СБИС - это доступ к документообороту от лица
юрлица. Хранить их открытым текстом в companies нельзя: любой, кто получит
дамп БД или доступ к настройкам компании, получит право подписывать и
отправлять первичку от имени компании.

Значения помечаются префиксом ENC_PREFIX, чтобы отличать зашифрованные от
легаси-открытых и позволять постепенную миграцию без простоя.
"""

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.core.config import settings

logger = logging.getLogger("spectech.crypto")

ENC_PREFIX = "enc::"


def _keys() -> list[bytes]:
    """Активный ключ и предыдущий (для ротации без простоя).

    В production отсутствие ENCRYPTION_KEY - ошибка запуска: тихий вывод
    ключа из jwt_secret_key означал бы, что ротация JWT молча превращает
    все секреты ЭДО в нерасшифровываемые, а компании уходят в stub.
    В dev/testing вывод допустим, чтобы не требовать настройки для тестов.
    """
    active = (getattr(settings, "ENCRYPTION_KEY", "") or "").strip()
    previous = (getattr(settings, "ENCRYPTION_KEY_PREVIOUS", "") or "").strip()
    if not active:
        env = (getattr(settings, "environment", "") or "").lower()
        if env == "production":
            raise RuntimeError(
                "ENCRYPTION_KEY is required in production: integration secrets "
                "must not depend on the JWT signing key"
            )
        material = (getattr(settings, "jwt_secret_key", "") or "").encode()
        if not material:
            raise RuntimeError(
                "Neither ENCRYPTION_KEY nor jwt_secret_key is configured"
            )
        logger.warning(
            "ENCRYPTION_KEY is not set - deriving from jwt_secret_key. "
            "Set a dedicated key before production."
        )
        active = base64.urlsafe_b64encode(hashlib.sha256(material).digest()).decode()
    keys = [active.encode()]
    if previous:
        keys.append(previous.encode())
    return keys


def _fernet() -> Fernet:
    """Шифрование активным ключом."""
    return Fernet(_keys()[0])


def _multi() -> MultiFernet:
    """Расшифровка любым из ключей - активным или предыдущим."""
    return MultiFernet([Fernet(k) for k in _keys()])


def rotate_secret(value: str | None) -> str:
    """Перешифровать значение активным ключом (для фоновой ротации)."""
    plain = decrypt_secret(value)
    return encrypt_secret(plain) if plain else ""


def encrypt_secret(plain: str | None) -> str:
    """Зашифровать секрет. Пустое значение остаётся пустым."""
    if not plain:
        return ""
    if plain.startswith(ENC_PREFIX):
        return plain
    return ENC_PREFIX + _fernet().encrypt(plain.encode()).decode()


def decrypt_secret(value: str | None) -> str:
    """Расшифровать секрет. Легаси-открытые значения отдаются как есть."""
    if not value:
        return ""
    if not value.startswith(ENC_PREFIX):
        return value
    try:
        return _multi().decrypt(value[len(ENC_PREFIX) :].encode()).decode()
    except InvalidToken:
        logger.error("Stored secret cannot be decrypted - wrong ENCRYPTION_KEY?")
        return ""


def mask_secret(value: str | None) -> str:
    """Маска для ответа API: последние 4 символа, никогда само значение."""
    plain = decrypt_secret(value)
    if not plain:
        return ""
    return f"****{plain[-4:]}" if len(plain) >= 4 else "****"


def ensure_keys_configured() -> None:
    """Fail-fast проверка ключей при старте (production).

    В production без ENCRYPTION_KEY вызывает RuntimeError — контейнер
    не должен подниматься. В dev/testing допустима derivation из JWT.
    """
    _keys()


def is_encrypted_with_active_key(value: str | None) -> bool:
    """Расшифровывается ли значение АКТИВНЫМ ключом (идемпотентная ротация)."""
    if not value or not value.startswith(ENC_PREFIX):
        return False
    try:
        Fernet(_keys()[0]).decrypt(value[len(ENC_PREFIX) :].encode())
        return True
    except InvalidToken:
        return False


def is_decryptable(value: str | None) -> bool:
    """Читается ли секрет активным или предыдущим ключом (UI-флаг).

    Пустое и легаси-открытое значения считаются читаемыми.
    """
    if not value or not value.startswith(ENC_PREFIX):
        return True
    return decrypt_secret(value) != ""
