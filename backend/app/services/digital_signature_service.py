"""Сервис подписания документов КЭП (CryptoPro / Госуслуги)."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DigitalSignatureService:
    """Подписание документов квалифицированной электронной подписью.
    
    Поддерживает:
    - CryptoPro CSP (через REST API криптопровайдера)
    - Госуслуги ЕПГУ (через ЕСИА API)
    - Stub-режим для разработки
    """

    def __init__(self):
        from app.core.config import settings
        self.provider = getattr(settings, "SIGNATURE_PROVIDER", "stub")  # cryptopro / gosuslugi / stub
        self.cryptopro_url = getattr(settings, "CRYPTOPRO_URL", "http://localhost:8080")
        self.gosuslugi_client_id = getattr(settings, "GOSUSLUGI_CLIENT_ID", "")
        self.gosuslugi_secret = getattr(settings, "GOSUSLUGI_SECRET", "")
        self.enabled = self.provider != "stub"

    async def sign_document(self, document_bytes: bytes, certificate_thumbprint: str = "") -> dict:
        """Подписать документ КЭП.
        
        Returns:
            {"signature": base64_string, "status": "signed"} или error
        """
        if self.provider == "cryptopro":
            return await self._sign_cryptopro(document_bytes, certificate_thumbprint)
        elif self.provider == "gosuslugi":
            return await self._sign_gosuslugi(document_bytes)
        else:
            logger.info("SIGNATURE STUB → signing %d bytes", len(document_bytes))
            import base64, hashlib
            # Stub: SHA256 hash как псевдо-подпись
            fake_sig = base64.b64encode(hashlib.sha256(document_bytes).digest()).decode()
            return {"signature": fake_sig, "status": "signed_stub", "provider": "stub"}

    async def _sign_cryptopro(self, document_bytes: bytes, thumbprint: str) -> dict:
        """Подписание через CryptoPro CSP REST API."""
        import httpx, base64
        try:
            payload = {
                "certificateThumbprint": thumbprint,
                "data": base64.b64encode(document_bytes).decode(),
                "signatureType": "CMS",
            }
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{self.cryptopro_url}/api/v1/sign",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
                sig = data.get("signature", "")
                logger.info("✅ CryptoPro signed: %d bytes signature", len(sig))
                return {"signature": sig, "status": "signed", "provider": "cryptopro"}
        except Exception as e:
            logger.error(f"❌ CryptoPro signing failed: {e}")
            return {"signature": "", "status": "error", "error": str(e)}

    async def _sign_gosuslugi(self, document_bytes: bytes) -> dict:
        """Подписание через Госуслуги (ЕСИА)."""
        import httpx, base64
        try:
            # Step 1: Get access token via ESIA OAuth
            async with httpx.AsyncClient(timeout=30) as client:
                token_resp = await client.post(
                    "https://esia.gosuslugi.ru/aas/oauth2/te",
                    data={
                        "client_id": self.gosuslugi_client_id,
                        "client_secret": self.gosuslugi_secret,
                        "grant_type": "client_credentials",
                        "scope": "crypto_sign",
                    },
                )
                token_resp.raise_for_status()
                access_token = token_resp.json().get("access_token", "")

                # Step 2: Sign document
                sign_resp = await client.post(
                    "https://esia.gosuslugi.ru/crypto/api/v1/sign",
                    json={"data": base64.b64encode(document_bytes).decode()},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                sign_resp.raise_for_status()
                data = sign_resp.json()
                sig = data.get("signature", "")
                logger.info("✅ Gosuslugi signed: %d bytes signature", len(sig))
                return {"signature": sig, "status": "signed", "provider": "gosuslugi"}
        except Exception as e:
            logger.error(f"❌ Gosuslugi signing failed: {e}")
            return {"signature": "", "status": "error", "error": str(e)}

    async def verify_signature(self, document_bytes: bytes, signature: str) -> dict:
        """Проверить подпись документа."""
        if self.provider == "stub":
            return {"valid": True, "provider": "stub"}

        # TODO: Real verification via CryptoPro/Gosuslugi
        logger.info("SIGNATURE VERIFY STUB")
        return {"valid": True, "provider": self.provider}


digital_signature_service = DigitalSignatureService()
