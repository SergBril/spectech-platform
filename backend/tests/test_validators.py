"""Unit-тесты для валидаторов."""

from app.utils.validators import (
    validate_inn,
    validate_kpp,
    validate_license_plate,
    validate_ogrn,
    validate_vin,
)


class TestValidateVIN:
    """Тесты для валидации VIN."""

    def test_valid_vin(self):
        """Валидный VIN должен проходить проверку."""
        # Пример валидного VIN (контрольная сумма верна)
        vin = "1HGBH41JXMN109186"
        is_valid, error = validate_vin(vin)
        assert is_valid is True
        assert error is None

    def test_invalid_length(self):
        """VIN неправильной длины должен отклоняться."""
        vin = "1HGBH41JXMN10918"  # 16 символов
        is_valid, error = validate_vin(vin)
        assert is_valid is False
        assert "17 символов" in error

    def test_invalid_characters(self):
        """VIN с недопустимыми символами (I, O, Q) должен отклоняться."""
        vin = "1HGBH41JIMN109186"  # содержит I
        is_valid, error = validate_vin(vin)
        assert is_valid is False
        assert "недопустимые символы" in error

    def test_invalid_checksum(self):
        """VIN с неверной контрольной суммой должен отклоняться."""
        vin = "1HGBH41JXMN109187"  # изменена последняя цифра
        is_valid, error = validate_vin(vin)
        assert is_valid is False
        assert "контрольная сумма" in error

    def test_empty_vin(self):
        """Пустой VIN должен отклоняться."""
        is_valid, error = validate_vin("")
        assert is_valid is False
        assert "не может быть пустым" in error

    def test_lowercase_conversion(self):
        """VIN в нижнем регистре должен конвертироваться в верхний."""
        vin = "1hgbh41jxmn109186"
        is_valid, error = validate_vin(vin)
        assert is_valid is True


class TestValidateINN:
    """Тесты для валидации ИНН."""

    def test_valid_inn_10_digits(self):
        """Валидный 10-значный ИНН должен проходить проверку."""
        inn = "7707083893"  # реальный ИНН Сбербанка
        is_valid, error = validate_inn(inn)
        assert is_valid is True
        assert error is None

    def test_valid_inn_12_digits(self):
        """Валидный 12-значный ИНН должен проходить проверку."""
        inn = "500100732259"  # пример 12-значного ИНН
        is_valid, error = validate_inn(inn)
        assert is_valid is True
        assert error is None

    def test_invalid_length(self):
        """ИНН неправильной длины должен отклоняться."""
        inn = "770708389"  # 9 цифр
        is_valid, error = validate_inn(inn)
        assert is_valid is False
        assert "10 или 12 цифр" in error

    def test_invalid_characters(self):
        """ИНН с буквами должен отклоняться."""
        inn = "770708389A"
        is_valid, error = validate_inn(inn)
        assert is_valid is False
        assert "только цифры" in error

    def test_invalid_checksum_10(self):
        """10-значный ИНН с неверной контрольной суммой должен отклоняться."""
        inn = "7707083894"  # изменена последняя цифра
        is_valid, error = validate_inn(inn)
        assert is_valid is False
        assert "контрольная сумма" in error

    def test_empty_inn(self):
        """Пустой ИНН должен отклоняться."""
        is_valid, error = validate_inn("")
        assert is_valid is False
        assert "не может быть пустым" in error


class TestValidateKPP:
    """Тесты для валидации КПП."""

    def test_valid_kpp(self):
        """Валидный КПП должен проходить проверку."""
        kpp = "770701001"
        is_valid, error = validate_kpp(kpp)
        assert is_valid is True
        assert error is None

    def test_invalid_length(self):
        """КПП неправильной длины должен отклоняться."""
        kpp = "77070100"  # 8 цифр
        is_valid, error = validate_kpp(kpp)
        assert is_valid is False
        assert "9 цифр" in error

    def test_invalid_characters(self):
        """КПП с буквами должен отклоняться."""
        kpp = "77070100A"
        is_valid, error = validate_kpp(kpp)
        assert is_valid is False
        assert "только цифры" in error

    def test_empty_kpp_allowed(self):
        """Пустой КПП должен быть допустим (опциональное поле)."""
        is_valid, error = validate_kpp("")
        assert is_valid is True
        assert error is None


class TestValidateOGRN:
    """Тесты для валидации ОГРН."""

    def test_valid_ogrn_13(self):
        """Валидный 13-значный ОГРН должен проходить проверку."""
        ogrn = "1027700132195"  # реальный ОГРН Сбербанка
        is_valid, error = validate_ogrn(ogrn)
        assert is_valid is True
        assert error is None

    def test_invalid_length(self):
        """ОГРН неправильной длины должен отклоняться."""
        ogrn = "102770013219"  # 12 цифр
        is_valid, error = validate_ogrn(ogrn)
        assert is_valid is False
        assert "13 или 15 цифр" in error

    def test_empty_ogrn_allowed(self):
        """Пустой ОГРН должен быть допустим (опциональное поле)."""
        is_valid, error = validate_ogrn("")
        assert is_valid is True
        assert error is None


class TestValidateLicensePlate:
    """Тесты для валидации гос. номеров."""

    def test_valid_plate_2_digit_region(self):
        """Валидный гос. номер с 2-значным регионом."""
        plate = "А123ВВ77"  # буквы А, В, В — все разрешены
        is_valid, error = validate_license_plate(plate)
        assert is_valid is True
        assert error is None

    def test_valid_plate_3_digit_region(self):
        """Валидный гос. номер с 3-значным регионом (Москва)."""
        plate = "А123ВВ777"  # буквы А, В, В — все разрешены
        is_valid, error = validate_license_plate(plate)
        assert is_valid is True
        assert error is None

    def test_valid_plate_all_allowed_letters(self):
        """Проверка всех разрешённых букв (АВЕКМНОРСТУХ)."""
        # Каждая из 12 разрешённых букв должна работать
        for letter in "АВЕКМНОРСТУХ":
            plate = f"{letter}123{letter}{letter}777"
            is_valid, error = validate_license_plate(plate)
            assert is_valid is True, f"Буква {letter} должна быть разрешена: {error}"

    def test_invalid_letter_B(self):
        """Буква Б НЕ используется в гос. номерах РФ."""
        plate = "А123БВ777"  # Б — запрещена
        is_valid, error = validate_license_plate(plate)
        assert is_valid is False
        assert "Неверный формат" in error

    def test_invalid_letter_D(self):
        """Буква Д НЕ используется в гос. номерах РФ."""
        plate = "Д123АВ777"
        is_valid, error = validate_license_plate(plate)
        assert is_valid is False

    def test_invalid_format_digits_first(self):
        """Неверный формат: цифры в начале."""
        plate = "123АВВ777"
        is_valid, error = validate_license_plate(plate)
        assert is_valid is False
        assert "Неверный формат" in error

    def test_invalid_latin_letters(self):
        """Латинские буквы не должны приниматься."""
        plate = "A123BB777"  # латиница
        is_valid, error = validate_license_plate(plate)
        assert is_valid is False

    def test_empty_plate(self):
        """Пустой гос. номер должен отклоняться."""
        is_valid, error = validate_license_plate("")
        assert is_valid is False
        assert "не может быть пустым" in error

    def test_lowercase_conversion(self):
        """Гос. номер в нижнем регистре должен конвертироваться."""
        plate = "а123вв777"  # нижний регистр
        is_valid, error = validate_license_plate(plate)
        assert is_valid is True

    def test_with_spaces(self):
        """Гос. номер с пробелами должен нормализоваться."""
        plate = "А 123 ВВ 777"
        is_valid, error = validate_license_plate(plate)
        assert is_valid is True
