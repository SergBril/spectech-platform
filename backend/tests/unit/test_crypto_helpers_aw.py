"""AW: fail-fast при старте, хелперы ротации/читаемости, guard в lifespan."""

from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

from app.core.crypto import (
    ENC_PREFIX,
    encrypt_secret,
    ensure_keys_configured,
    is_decryptable,
    is_encrypted_with_active_key,
)

pytestmark = [pytest.mark.unit]


def _settings(st, *, key="", previous="", env="production", jwt="jwt-secret"):
    st.ENCRYPTION_KEY = key
    st.ENCRYPTION_KEY_PREVIOUS = previous
    st.environment = env
    st.jwt_secret_key = jwt


class TestEnsureKeysConfigured:
    def test_production_without_key_raises(self):
        with patch("app.core.crypto.settings") as st:
            _settings(st)
            with pytest.raises(RuntimeError, match="ENCRYPTION_KEY is required"):
                ensure_keys_configured()

    def test_production_with_key_ok(self):
        with patch("app.core.crypto.settings") as st:
            _settings(st, key=Fernet.generate_key().decode())
            ensure_keys_configured()

    def test_dev_derivation_ok(self):
        with patch("app.core.crypto.settings") as st:
            _settings(st, env="development")
            ensure_keys_configured()


class TestActiveKeyHelper:
    def test_active_true_previous_false(self):
        old = Fernet.generate_key().decode()
        new = Fernet.generate_key().decode()
        with patch("app.core.crypto.settings") as st:
            _settings(st, key=old)
            sealed_old = encrypt_secret("k")
        with patch("app.core.crypto.settings") as st:
            _settings(st, key=new, previous=old)
            assert is_encrypted_with_active_key(sealed_old) is False
            sealed_new = encrypt_secret("k")
            assert is_encrypted_with_active_key(sealed_new) is True
            assert is_encrypted_with_active_key("legacy-plain") is False
            assert is_encrypted_with_active_key("") is False
            assert is_encrypted_with_active_key(None) is False


class TestIsDecryptable:
    def test_empty_and_plaintext_true(self):
        assert is_decryptable(None) is True
        assert is_decryptable("") is True
        assert is_decryptable("legacy-plain") is True

    def test_encrypted_true_with_key(self):
        with patch("app.core.crypto.settings") as st:
            _settings(st, key=Fernet.generate_key().decode())
            assert is_decryptable(encrypt_secret("k")) is True

    def test_wrong_key_false(self):
        with patch("app.core.crypto.settings") as st:
            _settings(st, key=Fernet.generate_key().decode())
            sealed = encrypt_secret("k")
        with patch("app.core.crypto.settings") as st:
            _settings(st, key=Fernet.generate_key().decode())
            assert is_decryptable(sealed) is False

    def test_garbage_false(self):
        with patch("app.core.crypto.settings") as st:
            _settings(st, key=Fernet.generate_key().decode())
            assert is_decryptable(ENC_PREFIX + "garbage") is False


class TestLifespanGuard:
    @pytest.mark.asyncio
    async def test_production_without_key_fails_fast(self):
        from app.main import app

        with (
            patch("app.main.settings") as st,
            patch(
                "app.core.crypto.ensure_keys_configured",
                side_effect=RuntimeError("ENCRYPTION_KEY is required in production"),
            ),
        ):
            st.environment = "production"
            with pytest.raises(RuntimeError, match="ENCRYPTION_KEY"):
                async with app.router.lifespan_context(app):
                    pass

    @pytest.mark.asyncio
    async def test_testing_skips_guard(self):
        from app.main import app

        with (
            patch("app.main.settings") as st,
            patch("app.core.crypto.ensure_keys_configured") as guard,
        ):
            st.environment = "testing"
            st.TESTING = True
            async with app.router.lifespan_context(app):
                guard.assert_not_called()
