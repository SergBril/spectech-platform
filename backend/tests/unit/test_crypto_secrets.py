"""Шифрование секретов интеграций: ключ ЭДО не должен лежать открытым текстом."""

from app.core.crypto import ENC_PREFIX, decrypt_secret, encrypt_secret, mask_secret


class TestRoundTrip:
    def test_encrypt_then_decrypt(self):
        assert (
            decrypt_secret(encrypt_secret("diadoc-key-abc123")) == "diadoc-key-abc123"
        )

    def test_ciphertext_is_not_the_plaintext(self):
        enc = encrypt_secret("diadoc-key-abc123")
        assert enc.startswith(ENC_PREFIX)
        assert "diadoc-key-abc123" not in enc

    def test_empty_stays_empty(self):
        assert encrypt_secret("") == ""
        assert encrypt_secret(None) == ""
        assert decrypt_secret("") == ""
        assert decrypt_secret(None) == ""

    def test_encrypting_twice_does_not_double_wrap(self):
        once = encrypt_secret("k")
        assert encrypt_secret(once) == once
        assert decrypt_secret(once) == "k"

    def test_legacy_plaintext_is_readable(self):
        # Значения, записанные до шифрования, должны продолжать работать.
        assert decrypt_secret("legacy-plain-key") == "legacy-plain-key"

    def test_undecryptable_value_does_not_raise(self):
        assert decrypt_secret(ENC_PREFIX + "not-a-valid-token") == ""


class TestMasking:
    def test_mask_shows_only_the_tail(self):
        assert mask_secret(encrypt_secret("diadoc-key-abc123")) == "****c123"

    def test_mask_never_contains_the_secret(self):
        secret = "super-secret-diadoc-key"
        assert secret not in mask_secret(encrypt_secret(secret))

    def test_short_secret_is_fully_hidden(self):
        assert mask_secret(encrypt_secret("abc")) == "****"

    def test_empty_masks_to_empty(self):
        assert mask_secret("") == ""
        assert mask_secret(None) == ""
