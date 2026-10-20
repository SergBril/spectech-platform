"""Маршруты для работы с адресами через DaData API."""

import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/addresses", tags=["addresses"])
logger = logging.getLogger("spectech.addresses")

DADATA_API_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs/suggest/address"


class AddressSuggestRequest(BaseModel):
    """Запрос на подсказки адресов."""

    query: str
    count: int = 7


@router.post("/suggest")
async def suggest_addresses(request: AddressSuggestRequest) -> dict[str, Any]:
    """
    Прокси к DaData API для получения подсказок адресов.

    Используется для обхода CORS ограничений браузера.
    """
    if not settings.DADATA_TOKEN:
        raise HTTPException(
            status_code=500, detail="DaData token is not configured"
        )

    if len(request.query) < 3:
        return {"suggestions": []}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(
                DADATA_API_URL,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Authorization": f"Token {settings.DADATA_TOKEN}",
                },
                json={
                    "query": request.query,
                    "count": request.count,
                    "from_bound": {"value": "city"},
                    "to_bound": {"value": "house"},
                },
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"DaData API error: {e}")
            raise HTTPException(
                status_code=502, detail=f"DaData API error: {str(e)}"
            )
