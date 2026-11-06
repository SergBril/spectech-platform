"""Coverage tests for translations."""


class TestTranslateUnit:
    """Cover translate_unit (lines 29-34)."""

    def test_known_units(self):
        from app.services.translations import translate_unit
        assert translate_unit("hourly") == "час"
        assert translate_unit("shift") == "смена"
        assert translate_unit("km") == "км"
        assert translate_unit("m2") == "м²"
        assert translate_unit("kg") == "кг"
        assert translate_unit("liter") == "л"
        assert translate_unit("day") == "день"
        assert translate_unit("month") == "мес"
        assert translate_unit("piece") == "шт"
        assert translate_unit("ton") == "т"

    def test_case_insensitive(self):
        from app.services.translations import translate_unit
        assert translate_unit("HOURLY") == "час"
        assert translate_unit("Shift") == "смена"

    def test_strips_whitespace(self):
        from app.services.translations import translate_unit
        assert translate_unit("  km  ") == "км"

    def test_unknown_returns_as_is(self):
        from app.services.translations import translate_unit
        assert translate_unit("gallon") == "gallon"
        assert translate_unit("custom_unit") == "custom_unit"

    def test_empty_returns_sht(self):
        from app.services.translations import translate_unit
        assert translate_unit("") == "шт"
        assert translate_unit(None) == "шт"

    def test_russian_passthrough(self):
        from app.services.translations import translate_unit
        assert translate_unit("шт") == "шт"


class TestUnitTranslationsDict:
    """Cover UNIT_TRANSLATIONS constant."""

    def test_dict_not_empty(self):
        from app.services.translations import UNIT_TRANSLATIONS
        assert len(UNIT_TRANSLATIONS) > 0
        assert "hourly" in UNIT_TRANSLATIONS
