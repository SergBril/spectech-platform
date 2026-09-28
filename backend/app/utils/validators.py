"""Валидаторы для справочников."""

import re


def validate_vin(vin: str) -> tuple[bool, str | None]:
    """
    Валидация VIN (Vehicle Identification Number).

    Правила:
    - 17 символов
    - Только заглавные буквы (кроме I, O, Q) и цифры
    - Проверка контрольной суммы (9-й символ)

    Returns:
        (is_valid, error_message)
    """
    if not vin:
        return False, "VIN не может быть пустым"

    vin = vin.upper().strip()

    if len(vin) != 17:
        return False, f"VIN должен содержать 17 символов, получено {len(vin)}"

    # Проверка допустимых символов (исключаем I, O, Q)
    if not re.match(r"^[A-HJ-NPR-Z0-9]{17}$", vin):
        return False, "VIN содержит недопустимые символы (I, O, Q запрещены)"

    # Таблица транслитерации для контрольной суммы
    transliteration = {
        "A": 1,
        "B": 2,
        "C": 3,
        "D": 4,
        "E": 5,
        "F": 6,
        "G": 7,
        "H": 8,
        "J": 1,
        "K": 2,
        "L": 3,
        "M": 4,
        "N": 5,
        "P": 7,
        "R": 9,
        "S": 2,
        "T": 3,
        "U": 4,
        "V": 5,
        "W": 6,
        "X": 7,
        "Y": 8,
        "Z": 9,
    }

    # Веса для каждой позиции
    weights = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]

    # Расчёт контрольной суммы
    total = 0
    for i, char in enumerate(vin):
        if char.isdigit():
            value = int(char)
        else:
            value = transliteration.get(char, 0)
        total += value * weights[i]

    check_digit = total % 11
    expected_check = "X" if check_digit == 10 else str(check_digit)

    # 9-й символ — контрольная цифра
    if vin[8] != expected_check:
        return (
            False,
            f"Неверная контрольная сумма VIN (ожидалось {expected_check}, получено {vin[8]})",
        )

    return True, None


def validate_inn(inn: str) -> tuple[bool, str | None]:
    """
    Валидация ИНН (10 или 12 цифр).

    Returns:
        (is_valid, error_message)
    """
    if not inn:
        return False, "ИНН не может быть пустым"

    inn = inn.strip()

    if not inn.isdigit():
        return False, "ИНН должен содержать только цифры"

    if len(inn) not in (10, 12):
        return False, f"ИНН должен содержать 10 или 12 цифр, получено {len(inn)}"

    # Коэффициенты для проверки
    if len(inn) == 10:
        coefficients = [2, 4, 10, 3, 5, 9, 4, 6, 8]
        checksum = sum(int(inn[i]) * coefficients[i] for i in range(9)) % 11 % 10
        if int(inn[9]) != checksum:
            return False, "Неверная контрольная сумма ИНН (10 цифр)"
    else:  # 12 цифр
        coefficients_11 = [7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        coefficients_12 = [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8]
        checksum_11 = sum(int(inn[i]) * coefficients_11[i] for i in range(10)) % 11 % 10
        checksum_12 = sum(int(inn[i]) * coefficients_12[i] for i in range(11)) % 11 % 10
        if int(inn[10]) != checksum_11 or int(inn[11]) != checksum_12:
            return False, "Неверная контрольная сумма ИНН (12 цифр)"

    return True, None


def validate_kpp(kpp: str) -> tuple[bool, str | None]:
    """
    Валидация КПП (9 цифр).

    Returns:
        (is_valid, error_message)
    """
    if not kpp:
        return True, None  # КПП опционален

    kpp = kpp.strip()

    if not kpp.isdigit():
        return False, "КПП должен содержать только цифры"

    if len(kpp) != 9:
        return False, f"КПП должен содержать 9 цифр, получено {len(kpp)}"

    return True, None


def validate_ogrn(ogrn: str) -> tuple[bool, str | None]:
    """
    Валидация ОГРН (13 или 15 цифр).

    Returns:
        (is_valid, error_message)
    """
    if not ogrn:
        return True, None  # ОГРН опционален

    ogrn = ogrn.strip()

    if not ogrn.isdigit():
        return False, "ОГРН должен содержать только цифры"

    if len(ogrn) not in (13, 15):
        return False, f"ОГРН должен содержать 13 или 15 цифр, получено {len(ogrn)}"

    # Проверка контрольной суммы
    if len(ogrn) == 13:
        checksum = int(ogrn[:12]) % 11 % 10
        if int(ogrn[12]) != checksum:
            return False, "Неверная контрольная сумма ОГРН (13 цифр)"
    else:  # 15 цифр (ОГРНИП)
        checksum = int(ogrn[:14]) % 13 % 10
        if int(ogrn[14]) != checksum:
            return False, "Неверная контрольная сумма ОГРНИП (15 цифр)"

    return True, None


def validate_license_plate(plate: str) -> tuple[bool, str | None]:
    """
    Валидация российского гос. номера (А123БВ777 или А123БВ777).

    Returns:
        (is_valid, error_message)
    """
    if not plate:
        return False, "Гос. номер не может быть пустым"

    plate = plate.upper().strip().replace(" ", "")

    # Паттерн: буква + 3 цифры + 2 буквы + 2-3 цифры региона
    pattern = r"^[АВЕКМНОРСТУХ]\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}$"

    if not re.match(pattern, plate):
        return False, "Неверный формат гос. номера (ожидается А123БВ777)"

    return True, None
