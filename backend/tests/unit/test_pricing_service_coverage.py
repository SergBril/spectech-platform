"""Coverage tests for pricing_service."""


class TestGetPreset:
    """Cover get_preset (lines 151-164)."""

    def test_known_region(self):
        from app.services.pricing_service import PricingService

        preset = PricingService.get_preset("Москва")
        assert preset["hourly_rate"] == 3500
        assert preset["shift_rate"] == 28000

    def test_none_returns_default(self):
        from app.services.pricing_service import PricingService

        preset = PricingService.get_preset(None)
        assert preset["hourly_rate"] == 2000

    def test_empty_string_returns_default(self):
        from app.services.pricing_service import PricingService

        preset = PricingService.get_preset("")
        assert preset["hourly_rate"] == 2000

    def test_unknown_region_returns_default(self):
        from app.services.pricing_service import PricingService

        preset = PricingService.get_preset("Камчатский край")
        assert preset["hourly_rate"] == 2000

    def test_fuzzy_match_partial(self):
        from app.services.pricing_service import PricingService

        # "москв" should fuzzy-match to "Москва"
        preset = PricingService.get_preset("москв")
        assert preset["hourly_rate"] == 3500

    def test_fuzzy_match_reverse(self):
        from app.services.pricing_service import PricingService

        # "Московская область" contains "Московская область" key
        preset = PricingService.get_preset("Московская область")
        assert preset["hourly_rate"] == 3200

    def test_returns_copy_not_reference(self):
        from app.services.pricing_service import PricingService

        p1 = PricingService.get_preset("Москва")
        p2 = PricingService.get_preset("Москва")
        p1["hourly_rate"] = 9999
        assert p2["hourly_rate"] == 3500


class TestCalculateEstimate:
    """Cover calculate_estimate (lines 166-235)."""

    def test_per_hour_with_duration(self):
        from app.services.pricing_service import PricingService

        result = PricingService.calculate_estimate(
            region="Москва",
            rate_type="per_hour",
            shift_duration_hours=10,
            num_shifts=2,
        )
        # 3500 * 10 * 2 = 70000 base + 10% fuel = 77000
        assert result["base_amount"] == 70000.0
        assert result["fuel_surcharge"] == 7000.0
        assert result["estimated_amount"] == 77000.0
        assert result["rate_source"] == "preset_hourly (Москва)"

    def test_per_shift(self):
        from app.services.pricing_service import PricingService

        result = PricingService.calculate_estimate(
            region="Москва",
            rate_type="per_shift",
            num_shifts=3,
        )
        # 28000 * 3 = 84000 base + 10% = 92400
        assert result["base_amount"] == 84000.0
        assert result["estimated_amount"] == 92400.0

    def test_custom_rate(self):
        from app.services.pricing_service import PricingService

        result = PricingService.calculate_estimate(
            region="Москва",
            rate_type="per_shift",
            custom_rate=5000,
            num_shifts=1,
        )
        assert result["rate_used"] == 5000.0
        assert result["rate_source"] == "custom"
        assert result["base_amount"] == 5000.0

    def test_fixed_type_uses_shift_rate(self):
        from app.services.pricing_service import PricingService

        result = PricingService.calculate_estimate(
            region=None,
            rate_type="fixed",
            num_shifts=2,
        )
        # Default shift_rate=16000 * 2 = 32000 + 5% = 33600
        assert result["base_amount"] == 32000.0
        assert result["estimated_amount"] == 33600.0
        assert "default" in result["rate_source"]

    def test_per_hour_no_duration(self):
        from app.services.pricing_service import PricingService

        result = PricingService.calculate_estimate(
            region="Москва",
            rate_type="per_hour",
            shift_duration_hours=None,
            num_shifts=1,
        )
        # per_hour without duration: rate * 1 * num_shifts = 3500
        assert result["base_amount"] == 3500.0

    def test_zero_custom_rate_uses_preset(self):
        from app.services.pricing_service import PricingService

        result = PricingService.calculate_estimate(
            region="Москва",
            rate_type="per_shift",
            custom_rate=0,
            num_shifts=1,
        )
        assert result["rate_used"] == 28000.0
        assert "preset" in result["rate_source"]

    def test_negative_custom_rate_uses_preset(self):
        from app.services.pricing_service import PricingService

        result = PricingService.calculate_estimate(
            region="Москва",
            rate_type="per_shift",
            custom_rate=-100,
            num_shifts=1,
        )
        assert result["rate_used"] == 28000.0


class TestGetAvailableRegions:
    """Cover get_available_regions (lines 237-end)."""

    def test_returns_list(self):
        from app.services.pricing_service import PricingService

        regions = PricingService.get_available_regions()
        assert isinstance(regions, list)
        assert len(regions) > 0

    def test_moscow_first(self):
        from app.services.pricing_service import PricingService

        regions = PricingService.get_available_regions()
        assert regions[0]["name"] == "Москва"
        assert regions[0]["is_priority"] is True

    def test_priority_regions_come_first(self):
        from app.services.pricing_service import PricingService

        regions = PricingService.get_available_regions()
        priority_names = [
            "Москва",
            "Московская область",
            "Санкт-Петербург",
            "Ленинградская область",
        ]
        first_four = [r["name"] for r in regions[:4]]
        for name in priority_names:
            assert name in first_four

    def test_non_priority_sorted(self):
        from app.services.pricing_service import PricingService

        regions = PricingService.get_available_regions()
        non_priority = [r for r in regions if not r["is_priority"]]
        names = [r["name"] for r in non_priority]
        assert names == sorted(names)

    def test_all_have_required_fields(self):
        from app.services.pricing_service import PricingService

        regions = PricingService.get_available_regions()
        for r in regions:
            assert "name" in r
            assert "hourly_rate" in r
            assert "shift_rate" in r
            assert "is_priority" in r
