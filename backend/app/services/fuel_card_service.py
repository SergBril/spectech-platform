"""Интеграция с API топливных карт и АЗС."""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, UTC

logger = logging.getLogger(__name__)


class FuelCardService:
    """Сервис интеграции с провайдерами топливных карт (stub)."""

    SUPPORTED_PROVIDERS = ["gazpromneft", "lukoil", "rosneft", "tatneft", "custom"]

    def __init__(self):
        from app.core.config import settings
        self.api_key = getattr(settings, "FUEL_CARD_API_KEY", "")
        self.provider = getattr(settings, "FUEL_CARD_PROVIDER", "custom")
        self.enabled = bool(self.api_key)

    async def fetch_transactions(self, date_from: str, date_to: str, card_numbers: list[str] | None = None) -> list[dict]:
        """Получить транзакции с топливных карт от провайдера."""
        if not self.enabled:
            logger.info(f"FUEL CARD STUB → fetch {date_from} to {date_to}")
            return []

        import httpx

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                if self.provider == "gazpromneft":
                    return await self._fetch_gazpromneft(client, date_from, date_to, card_numbers)
                elif self.provider == "lukoil":
                    return await self._fetch_lukoil(client, date_from, date_to, card_numbers)
                else:
                    logger.warning(f"Provider {self.provider} not implemented, using stub")
                    return []
        except Exception as e:
            logger.error(f"Fuel card API error ({self.provider}): {e}")
            return []

    async def _fetch_gazpromneft(self, client: httpx.AsyncClient, date_from: str, date_to: str, card_numbers: list[str] | None) -> list[dict]:
        """Газпромнефть API v2: GET /api/v2/transactions."""
        from app.core.config import settings
        base_url = getattr(settings, "FUEL_CARD_BASE_URL", "https://api.gpnbonus.ru")

        params = {"date_from": date_from, "date_to": date_to, "limit": 1000}
        if card_numbers:
            params["card_numbers"] = ",".join(card_numbers)

        resp = await client.get(
            f"{base_url}/api/v2/transactions",
            headers={"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"},
            params=params,
        )
        resp.raise_for_status()
        data = resp.json()

        transactions = []
        for item in data.get("items", data if isinstance(data, list) else []):
            transactions.append({
                "vehicle_plate": item.get("vehicle_reg_number", item.get("plate", "")),
                "card_number": item.get("card_number", ""),
                "date": item.get("transaction_date", item.get("date", ""))[:10],
                "liters": float(item.get("volume", item.get("quantity", 0))),
                "fuel_type": item.get("fuel_type", "diesel").lower(),
                "odometer": float(item.get("odometer", 0)) if item.get("odometer") else None,
                "amount": float(item.get("amount", 0)),
                "station": item.get("station_name", ""),
            })

        logger.info(f"GazpromNeft: fetched {len(transactions)} transactions")
        return transactions

    async def _fetch_lukoil(self, client: httpx.AsyncClient, date_from: str, date_to: str, card_numbers: list[str] | None) -> list[dict]:
        """Лукойл API: POST /api/v1/reports/fuel-transactions."""
        from app.core.config import settings
        base_url = getattr(settings, "FUEL_CARD_BASE_URL", "https://api.lukoil-card.ru")

        payload = {"period_start": date_from, "period_end": date_to}
        if card_numbers:
            payload["cards"] = card_numbers

        resp = await client.post(
            f"{base_url}/api/v1/reports/fuel-transactions",
            headers={"X-API-Key": self.api_key, "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

        transactions = []
        for item in data.get("data", data if isinstance(data, list) else []):
            transactions.append({
                "vehicle_plate": item.get("gos_number", ""),
                "card_number": item.get("card_num", ""),
                "date": item.get("operation_date", "")[:10],
                "liters": float(item.get("volume_litres", 0)),
                "fuel_type": item.get("fuel_code", "diesel"),
                "odometer": float(item.get("mileage", 0)) if item.get("mileage") else None,
                "amount": float(item.get("sum_nds", 0)),
                "station": item.get("azs_name", ""),
            })

        logger.info(f"Lukoil: fetched {len(transactions)} transactions")
        return transactions

    async def sync_to_shift_entries(self, db: Session, company_id: int, transactions: list[dict]) -> dict:
        """Синхронизировать транзакции с записями расхода топлива по сменам."""
        from app.models.shift import ShiftFuelEntry, ShiftTask
        from app.models.vehicle import Vehicle

        synced = 0
        skipped = 0

        for txn in transactions:
            # Match transaction to shift by vehicle + date
            vehicle = db.execute(
                select(Vehicle).where(
                    Vehicle.company_id == company_id,
                    Vehicle.plate_number == txn.get("vehicle_plate", ""),
                )
            ).scalar_one_or_none()

            if not vehicle:
                skipped += 1
                continue

            shift = db.execute(
                select(ShiftTask).where(
                    ShiftTask.vehicle_id == vehicle.id,
                    ShiftTask.shift_date == txn.get("date"),
                )
            ).scalars().first()

            if not shift:
                skipped += 1
                continue

            # Check duplicate
            existing = db.execute(
                select(ShiftFuelEntry).where(
                    ShiftFuelEntry.shift_task_id == shift.id,
                    ShiftFuelEntry.quantity_liters == txn.get("liters", 0),
                )
            ).scalar_one_or_none()

            if existing:
                skipped += 1
                continue

            entry = ShiftFuelEntry(
                shift_task_id=shift.id,
                vehicle_id=vehicle.id,
                fuel_type=txn.get("fuel_type", "diesel"),
                quantity_liters=txn.get("liters", 0),
                odometer_reading=txn.get("odometer"),
                notes=f"Auto-sync from {self.provider}: card {txn.get('card_number', '')}",
            )
            db.add(entry)
            synced += 1

        db.commit()
        logger.info(f"Fuel card sync: {synced} synced, {skipped} skipped")
        return {"synced": synced, "skipped": skipped}


fuel_card_service = FuelCardService()
