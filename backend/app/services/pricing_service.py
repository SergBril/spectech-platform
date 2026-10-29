"""Сервис региональных ценовых пресетов и авто-расчёта стоимости заявок."""

import logging
from decimal import Decimal
from typing import Optional

logger = logging.getLogger("spectech.pricing")


# === Региональные пресеты цен ===
# Формат: region_key -> {hourly_rate, shift_rate, min_shift_hours, fixed_rates}
REGIONAL_PRICING_PRESETS: dict[str, dict] = {
    # Москва и МО — приоритетные регионы
    "Москва": {
        "hourly_rate": 3500,
        "shift_rate": 28000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 10,
    },
    "Московская область": {
        "hourly_rate": 3200,
        "shift_rate": 25000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 10,
    },
    # Санкт-Петербург и ЛО
    "Санкт-Петербург": {
        "hourly_rate": 3000,
        "shift_rate": 24000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 8,
    },
    "Ленинградская область": {
        "hourly_rate": 2800,
        "shift_rate": 22000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 8,
    },
    # Центральный ФО
    "Тульская область": {
        "hourly_rate": 2500,
        "shift_rate": 20000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 5,
    },
    "Калужская область": {
        "hourly_rate": 2500,
        "shift_rate": 20000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 5,
    },
    "Тверская область": {
        "hourly_rate": 2400,
        "shift_rate": 19000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 5,
    },
    "Рязанская область": {
        "hourly_rate": 2300,
        "shift_rate": 18000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 5,
    },
    "Владимирская область": {
        "hourly_rate": 2400,
        "shift_rate": 19000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 5,
    },
    "Смоленская область": {
        "hourly_rate": 2300,
        "shift_rate": 18000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 5,
    },
    "Брянская область": {
        "hourly_rate": 2200,
        "shift_rate": 17000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 5,
    },
    "Орловская область": {
        "hourly_rate": 2200,
        "shift_rate": 17000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 5,
    },
    "Курская область": {
        "hourly_rate": 2200,
        "shift_rate": 17000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 5,
    },
    "Белгородская область": {
        "hourly_rate": 2300,
        "shift_rate": 18000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 5,
    },
    "Липецкая область": {
        "hourly_rate": 2300,
        "shift_rate": 18000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 5,
    },
    "Воронежская область": {
        "hourly_rate": 2400,
        "shift_rate": 19000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 5,
    },
    "Ярославская область": {
        "hourly_rate": 2400,
        "shift_rate": 19000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 5,
    },
    "Ивановская область": {
        "hourly_rate": 2200,
        "shift_rate": 17000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 5,
    },
    "Костромская область": {
        "hourly_rate": 2100,
        "shift_rate": 16000,
        "min_shift_hours": 8,
        "fuel_surcharge_pct": 5,
    },
    # Волгоград
    "Волгоградская область": {
        "hourly_rate": 2000,
        "shift_rate": 16000,
        "min_shift_hours": 4,
        "fuel_surcharge_pct": 5,
    },
}

# Дефолтный пресет для регионов без специальных цен
DEFAULT_PRICING = {
    "hourly_rate": 2000,
    "shift_rate": 16000,
    "min_shift_hours": 4,
    "fuel_surcharge_pct": 5,
}


class PricingService:
    """Сервис расчёта стоимости заявок по региональным пресетам."""

    @staticmethod
    def get_preset(region: str | None) -> dict:
        """Получить ценовой пресет для региона."""
        if not region:
            return DEFAULT_PRICING.copy()
        preset = REGIONAL_PRICING_PRESETS.get(region)
        if preset:
            return preset.copy()
        # Fuzzy match: try partial match
        for key, val in REGIONAL_PRICING_PRESETS.items():
            if key.lower() in region.lower() or region.lower() in key.lower():
                logger.info(f"Fuzzy matched region '{region}' -> '{key}'")
                return val.copy()
        return DEFAULT_PRICING.copy()

    @staticmethod
    def calculate_estimate(
        region: str | None,
        rate_type: str,
        shift_duration_hours: float | None = None,
        custom_rate: float | None = None,
        num_shifts: int = 1,
    ) -> dict:
        """
        Рассчитать ориентировочную стоимость заявки.

        Args:
            region: Регион объекта
            rate_type: per_hour, per_shift, fixed
            shift_duration_hours: Длительность смены в часах
            custom_rate: Пользовательская ставка (если задана — используется вместо пресета)
            num_shifts: Количество смен

        Returns:
            dict с расчётом: estimated_amount, rate_used, breakdown
        """
        preset = PricingService.get_preset(region)

        if custom_rate is not None and custom_rate > 0:
            rate = Decimal(str(custom_rate))
            rate_source = "custom"
        elif rate_type == "per_hour":
            rate = Decimal(str(preset["hourly_rate"]))
            rate_source = f"preset_hourly ({region or 'default'})"
        elif rate_type == "per_shift":
            rate = Decimal(str(preset["shift_rate"]))
            rate_source = f"preset_shift ({region or 'default'})"
        else:
            rate = Decimal(str(preset["shift_rate"]))
            rate_source = f"preset_shift_default ({region or 'default'})"

        # Calculate based on rate type
        if rate_type == "per_hour" and shift_duration_hours:
            base_amount = rate * Decimal(str(shift_duration_hours)) * Decimal(str(num_shifts))
        elif rate_type == "per_shift":
            base_amount = rate * Decimal(str(num_shifts))
        else:
            # Default: shift rate * num_shifts
            hours = shift_duration_hours or preset["min_shift_hours"]
            base_amount = rate * Decimal(str(num_shifts))

        # Fuel surcharge
        fuel_pct = Decimal(str(preset.get("fuel_surcharge_pct", 5))) / Decimal("100")
        fuel_surcharge = (base_amount * fuel_pct).quantize(Decimal("0.01"))
        total = base_amount + fuel_surcharge

        result = {
            "estimated_amount": float(total.quantize(Decimal("0.01"))),
            "base_amount": float(base_amount.quantize(Decimal("0.01"))),
            "fuel_surcharge": float(fuel_surcharge),
            "rate_used": float(rate),
            "rate_type": rate_type or "per_shift",
            "rate_source": rate_source,
            "region": region,
            "num_shifts": num_shifts,
            "shift_duration_hours": shift_duration_hours,
        }

        logger.info(
            f"Pricing calc: region={region}, type={rate_type}, "
            f"amount={result['estimated_amount']}, source={rate_source}"
        )
        return result

    @staticmethod
    def get_available_regions() -> list[dict]:
        """Список доступных регионов с ценами (для frontend dropdown)."""
        regions = []
        # Moscow first
        for key in ["Москва", "Московская область", "Санкт-Петербург", "Ленинградская область"]:
            if key in REGIONAL_PRICING_PRESETS:
                p = REGIONAL_PRICING_PRESETS[key]
                regions.append({
                    "name": key,
                    "hourly_rate": p["hourly_rate"],
                    "shift_rate": p["shift_rate"],
                    "is_priority": True,
                })
        # Rest alphabetically
        for key in sorted(REGIONAL_PRICING_PRESETS.keys()):
            if key not in ["Москва", "Московская область", "Санкт-Петербург", "Ленинградская область"]:
                p = REGIONAL_PRICING_PRESETS[key]
                regions.append({
                    "name": key,
                    "hourly_rate": p["hourly_rate"],
                    "shift_rate": p["shift_rate"],
                    "is_priority": False,
                })
        return regions


pricing_service = PricingService()
