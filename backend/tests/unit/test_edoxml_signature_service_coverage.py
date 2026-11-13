"""Unit tests for edoxml/signature_service.py coverage gaps."""

from unittest.mock import patch


class TestSignatureServiceEnsureCertificate:
    """Cover lines 37-85: ensure_test_certificate() generation path."""

    def test_ensure_certificate_creates_new_files(self, tmp_path):
        """Cover lines 37-85: certificate generation when files don't exist."""
        with patch("app.services.edoxml.signature_service.CERTS_DIR", tmp_path):
            with patch(
                "app.services.edoxml.signature_service.PRIVATE_KEY_FILE",
                tmp_path / "private.pem",
            ):
                with patch(
                    "app.services.edoxml.signature_service.CERTIFICATE_FILE",
                    tmp_path / "cert.pem",
                ):
                    from app.services.edoxml import signature_service

                    signature_service.ensure_test_certificate()

                    assert (tmp_path / "private.pem").exists()
                    assert (tmp_path / "cert.pem").exists()

    def test_ensure_certificate_skips_if_exists(self, tmp_path):
        """Cover lines 35-36: early return when files already exist."""
        private_key_file = tmp_path / "private.pem"
        cert_file = tmp_path / "cert.pem"

        private_key_file.write_bytes(b"dummy key")
        cert_file.write_bytes(b"dummy cert")

        with patch("app.services.edoxml.signature_service.CERTS_DIR", tmp_path):
            with patch(
                "app.services.edoxml.signature_service.PRIVATE_KEY_FILE",
                private_key_file,
            ):
                with patch(
                    "app.services.edoxml.signature_service.CERTIFICATE_FILE", cert_file
                ):
                    from app.services.edoxml import signature_service

                    signature_service.ensure_test_certificate()

                    assert private_key_file.read_bytes() == b"dummy key"
                    assert cert_file.read_bytes() == b"dummy cert"


class TestSignatureServiceLoadKeys:
    """Cover lines 88-100: load_private_key and load_certificate."""

    def test_load_private_key_calls_ensure(self, tmp_path):
        """Cover line 88-91: load_private_key calls ensure_test_certificate."""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        private_key_file = tmp_path / "private.pem"
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_key_file.write_bytes(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

        with patch(
            "app.services.edoxml.signature_service.PRIVATE_KEY_FILE", private_key_file
        ):
            from app.services.edoxml import signature_service

            with patch.object(
                signature_service, "ensure_test_certificate"
            ) as mock_ensure:
                key = signature_service.load_private_key()

                assert mock_ensure.called
                assert key is not None


class TestSignatureServiceVerify:
    """Cover lines 156-219: verify_detached_signature edge cases."""

    def test_verify_exception_returns_false(self):
        """Cover lines 220-222: exception in verification returns False."""
        from app.services.edoxml import signature_service

        # Invalid signature data will cause exception in pkcs7.load_der_pkcs7_certificates
        result = signature_service.verify_detached_signature(
            data=b"test data", signature=b"invalid signature bytes"
        )

        # Should catch exception and return False
        assert result is False


class TestSignatureServiceGetInfo:
    """Cover lines 250-252: get_signature_info exception path."""

    def test_get_signature_info_exception(self):
        """Cover lines 250-252: exception in get_signature_info returns error dict."""
        from app.services.edoxml import signature_service

        with patch.object(
            signature_service, "load_certificate", side_effect=Exception("Test error")
        ):
            result = signature_service.get_signature_info()

            assert "error" in result
            assert "Test error" in result["error"]
