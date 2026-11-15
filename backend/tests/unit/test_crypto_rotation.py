"""Ротация ключа шифрования и fail-fast в production."""

from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from app.core.crypto import (
    decrypt_secret,
    encrypt_secret,
    rotate_secret,
)


class TestRotation:
    def test_value_encrypted_with_the_old_key_still_decrypts(self):
        old_key = Fernet.generate_key().decode()
        with patch("app.core.crypto.settings") as st:
            st.ENCRYPTION_KEY = old_key
            st.ENCRYPTION_KEY_PREVIOUS = ""
            st.environment = "production"
            sealed = encrypt_secret("diadoc-key-old")

        new_key = Fernet.generate_key().decode()
        with patch("app.core.crypto.settings") as st:
            st.ENCRYPTION_KEY = new_key
            st.ENCRYPTION_KEY_PREVIOUS = old_key
            st.environment = "production"
            assert decrypt_secret(sealed) == "diadoc-key-old"
            resealed = rotate_secret(sealed)
            assert decrypt_secret(resealed) == "diadoc-key-old"

        # после уборки previous значение, перешифрованное новым, читается
        with patch("app.core.crypto.settings") as st:
            st.ENCRYPTION_KEY = new_key
            st.ENCRYPTION_KEY_PREVIOUS = ""
            st.environment = "production"
            assert decrypt_secret(resealed) == "diadoc-key-old"

    def test_without_the_old_key_the_value_is_unreadable(self):
        old_key = Fernet.generate_key().decode()
        with patch("app.core.crypto.settings") as st:
            st.ENCRYPTION_KEY = old_key
            st.ENCRYPTION_KEY_PREVIOUS = ""
            st.environment = "production"
            sealed = encrypt_secret("k")
        with patch("app.core.crypto.settings") as st:
            st.ENCRYPTION_KEY = Fernet.generate_key().decode()
            st.ENCRYPTION_KEY_PREVIOUS = ""
            st.environment = "production"
            assert decrypt_secret(sealed) == ""


class TestProductionGuard:
    def test_production_without_a_key_raises(self):
        with patch("app.core.crypto.settings") as st:
            st.ENCRYPTION_KEY = ""
            st.ENCRYPTION_KEY_PREVIOUS = ""
            st.environment = "production"
            st.jwt_secret_key = "jwt-secret"
            with pytest.raises(RuntimeError, match="ENCRYPTION_KEY is required"):
                encrypt_secret("k")

    def test_dev_derives_and_warns(self):
        with patch("app.core.crypto.settings") as st:
            st.ENCRYPTION_KEY = ""
            st.ENCRYPTION_KEY_PREVIOUS = ""
            st.environment = "development"
            st.jwt_secret_key = "jwt-secret"
            assert decrypt_secret(encrypt_secret("k")) == "k"
