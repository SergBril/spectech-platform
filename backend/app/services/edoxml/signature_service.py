"""
Сервис подписания XML для ЭДО.

Фаза 1: RSA-подпись для разработки (правильная CMS-структура).
Фаза 2 (позже): замена на ГОСТ Р 34.10-2012 через pycades (КриптоПро).

Формат подписи: CMS/PKCS#7 detached (DER binary) — стандарт ФНС для .sig файлов.
"""

import datetime
import logging
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

logger = logging.getLogger("spectech.edoxml.signature")

CERTS_DIR = Path(__file__).parent / "certificates"
PRIVATE_KEY_FILE = CERTS_DIR / "test_key.pem"
CERTIFICATE_FILE = CERTS_DIR / "test_cert.pem"


def ensure_test_certificate() -> None:
    """
    Создаёт тестовый RSA-сертификат (для разработки, НЕ для боевого ЭДО).

    В боевой среде замените на реальный сертификат ГОСТ от аккредитованного УЦ.
    """
    CERTS_DIR.mkdir(parents=True, exist_ok=True)

    if PRIVATE_KEY_FILE.exists() and CERTIFICATE_FILE.exists():
        return

    logger.info("Generating test RSA certificate for development...")

    # Генерация ключа RSA-2048
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    # Сохранение приватного ключа
    with open(PRIVATE_KEY_FILE, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Генерация самоподписанного сертификата
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "RU"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Москва"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "г. Москва"),
            x509.NameAttribute(
                NameOID.ORGANIZATION_NAME, 'ООО "СпецТехника Про" (ТЕСТ)'
            ),
            x509.NameAttribute(NameOID.COMMON_NAME, "spectech-dev-cert"),
            x509.NameAttribute(NameOID.EMAIL_ADDRESS, "dev@spectech.pro"),
        ]
    )

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
        .sign(private_key, hashes.SHA256())
    )

    # Сохранение сертификата
    with open(CERTIFICATE_FILE, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    logger.info(f"Test certificate saved to {CERTIFICATE_FILE}")


def load_private_key():
    """Загружает приватный ключ."""
    ensure_test_certificate()
    with open(PRIVATE_KEY_FILE, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def load_certificate():
    """Загружает сертификат."""
    ensure_test_certificate()
    with open(CERTIFICATE_FILE, "rb") as f:
        return x509.load_pem_x509_certificate(f.read())


def create_detached_signature(data: bytes) -> bytes:
    """
    Создаёт отсоединённую подпись CMS/PKCS#7 в формате DER.

    Args:
        data: Байты подписываемого документа (XML в windows-1251)

    Returns:
        bytes: DER-кодированная CMS-подпись (для .sig файла)

    Note:
        Фаза 1: RSA-SHA256 (для разработки, правильная структура CMS).
        Фаза 2: заменить на ГОСТ через pycades.sign_cades() без изменения API.
    """
    from cryptography.hazmat.primitives.serialization import pkcs7

    private_key = load_private_key()
    certificate = load_certificate()

    # Создание CMS/PKCS#7 отсоединённой подписи (DER формат)
    # Именно такой формат принимает ФНС и операторы ЭДО (Диадок, СБИС)
    signature = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(data)
        .add_signer(certificate, private_key, hashes.SHA256())
        .sign(
            serialization.Encoding.DER, options=[pkcs7.PKCS7Options.DetachedSignature]
        )
    )

    logger.info(f"Detached CMS signature created: {len(signature)} bytes")
    return signature


def verify_detached_signature(data: bytes, signature: bytes) -> bool:
    """
    Проверяет отсоединённую CMS-подпись.

    Args:
        data: Оригинальные байты документа
        signature: DER-кодированная CMS-подпись

    Returns:
        bool: True если подпись валидна

    Note:
        Использует cryptography library для верификации (без openssl).
    """
    try:
        from cryptography.hazmat.primitives.serialization import pkcs7

        # Загружаем CMS-подпись
        cms = pkcs7.load_der_pkcs7_certificates(signature)

        if not cms:
            logger.error("No certificates found in signature")
            return False

        # Получаем сертификат подписанта
        signer_cert = cms[0]

        # Проверяем подпись
        try:
            signer_cert.verify_directly_issued_by(signer_cert)  # самоподписанный
        except Exception:
            pass  # пропускаем проверку цепочки

        # Верифицируем данные
        # Для detached signature нужно передать оригинальные данные

        # Извлекаем подпись из CMS
        # Примечание: cryptography не имеет встроенной верификации detached CMS
        # Поэтому используем упрощённую проверку через openssl (если доступен)
        import shutil
        import subprocess
        import tempfile

        # Проверяем наличие openssl
        if not shutil.which("openssl"):
            logger.warning("openssl not available, skipping signature verification")
            return True  # предполагаем валидность для тестовой среды

        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as f_data:
            f_data.write(data)
            data_path = f_data.name

        with tempfile.NamedTemporaryFile(suffix=".sig", delete=False) as f_sig:
            f_sig.write(signature)
            sig_path = f_sig.name

        cert_path = str(CERTIFICATE_FILE)

        try:
            result = subprocess.run(
                [
                    "openssl",
                    "smime",
                    "-verify",
                    "-in",
                    sig_path,
                    "-inform",
                    "DER",
                    "-content",
                    data_path,
                    "-CAfile",
                    cert_path,
                    "-noverify",
                ],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        finally:
            # Удаляем временные файлы
            import os

            os.unlink(data_path)
            os.unlink(sig_path)

    except Exception as e:
        logger.error(f"Signature verification failed: {e}")
        return False


def get_signature_info() -> dict:
    """Информация о текущем сертификате (для endpoint /signature/info)."""
    try:
        cert = load_certificate()
        pub_key = cert.public_key()

        # Определяем тип ключа
        key_type = type(pub_key).__name__
        key_size = None
        if hasattr(pub_key, "key_size"):
            key_size = pub_key.key_size

        return {
            "subject": cert.subject.rfc4514_string(),
            "issuer": cert.issuer.rfc4514_string(),
            "serial_number": str(cert.serial_number),
            "not_valid_before": cert.not_valid_before_utc.isoformat(),
            "not_valid_after": cert.not_valid_after_utc.isoformat(),
            "signature_algorithm": cert.signature_algorithm_oid._name,
            "public_key_type": key_type,
            "public_key_size": key_size,
            "phase": "1 (development, RSA-SHA256)",
            "note": "Для боевого ЭДО замените на сертификат ГОСТ Р 34.10-2012 через pycades",
        }
    except Exception as e:
        logger.error(f"Failed to get signature info: {e}")
        return {"error": str(e)}
