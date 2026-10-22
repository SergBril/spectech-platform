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

        # TODO: Реальная интеграция с API провайдера
        # Пример для Газпромнефть:
        # resp = await client.get("/api/v2/transactions", params={...})
        logger.info(f"FUEL CARD API → {self.provider}: {date_from} to {date_to}")
        return []

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
