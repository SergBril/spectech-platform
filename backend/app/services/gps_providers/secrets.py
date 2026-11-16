"""Секреты GPS-конфига: шифрование при записи, расшифровка при использовании.

Legacy-значения без префикса enc:: читаются КАК ЕСТЬ. decrypt_secret на
нечитаемом значении возвращает "" — если применить его к plaintext-паролю,
провайдер молча перестанет авторизоваться. Поэтому расшифровываем только
помеченные значения, а остальные пропускаем нетронутыми.
"""

from typing import Any

from app.core.crypto import ENC_PREFIX, decrypt_secret, encrypt_secret

GPS_SECRET_KEYS = ("password", "api_key", "token", "webhook_secret")


def encrypt_gps_secrets(cfg: dict[str, Any] | None) -> dict[str, Any] | None:
    """Зашифровать секреты перед сохранением. Уже зашифрованные не трогаем."""
    if cfg is None:
        return None
    out = dict(cfg)
    for key in GPS_SECRET_KEYS:
        value = out.get(key)
        if isinstance(value, str) and value and not value.startswith(ENC_PREFIX):
            out[key] = encrypt_secret(value)
    return out


def decrypt_gps_secrets(cfg: dict[str, Any] | None) -> dict[str, Any] | None:
    """Расшифровать секреты для адаптера. Plaintext-legacy проходит как есть."""
    if cfg is None:
        return None
    out = dict(cfg)
    for key in GPS_SECRET_KEYS:
        value = out.get(key)
        if isinstance(value, str) and value.startswith(ENC_PREFIX):
            out[key] = decrypt_secret(value)
    return out
