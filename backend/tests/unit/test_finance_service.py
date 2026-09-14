"""Unit тесты для finance_service."""

from datetime import UTC

import pytest


class TestDocumentNumberGeneration:
    """Тесты генерации номеров документов."""

    def test_generate_invoice_number_format(self, db_session):
        """Проверяем формат номера инвойса."""
        from app.services.finance_service import generate_document_number

        number = generate_document_number(db_session, "INV")

        assert number is not None
        assert number.startswith("INV-")
        # Формат: INV-YYYY-NNNN
        parts = number.split("-")
        assert len(parts) == 3
        assert parts[0] == "INV"
        assert len(parts[1]) == 4  # Год
        assert parts[2].isdigit()  # Порядковый номер

    def test_generate_act_number_format(self, db_session):
        """Проверяем формат номера акта."""
        from app.services.finance_service import generate_document_number

        number = generate_document_number(db_session, "ACT")

        assert number.startswith("ACT-")
        parts = number.split("-")
        assert len(parts) == 3

    def test_unique_numbers(self, db_session):
        """Каждый новый номер должен быть уникальным при создании реальных документов."""
        from datetime import datetime, timedelta
        from decimal import Decimal

        from app.models.dispatch import Request
        from app.models.finance import Invoice
        from app.services.finance_service import generate_document_number

        now = datetime.now(UTC)

        # Создаём тестовый Request для привязки Invoice
        request = Request(
            client_id=1,
            work_type="Test work",
            object_address="Test address",
            planned_start=now,
            planned_end=now + timedelta(days=1),
            status="new",
            request_type="one_time",
            source_channel="phone",
            priority="normal",
            company_id=1,
            rate_type="hourly",
        )
        db_session.add(request)
        db_session.commit()
        db_session.refresh(request)

        numbers = []
        for i in range(5):
            # Генерируем номер
            num = generate_document_number(db_session, "INV")
            numbers.append(num)

            # Создаём Invoice со ВСЕМИ обязательными полями
            invoice = Invoice(
                document_number=num,
                request_id=request.id,
                client_id=1,
                company_id=1,
                subtotal=Decimal("1000.00"),
                vat_amount=Decimal("0.00"),
                total=Decimal("1000.00"),
                paid_amount=Decimal("0.00"),
                invoice_date=now,
                due_date=now + timedelta(days=30),
                status="draft",
                created_by=1,
            )
            db_session.add(invoice)
            db_session.commit()

        # Все 5 номеров должны быть разными
        unique_numbers = set(numbers)
        assert len(unique_numbers) == 5, f"Got duplicates: {numbers}"

        # Проверяем последовательность
        for i in range(1, len(numbers)):
            prev_num = int(numbers[i - 1].split("-")[-1])
            curr_num = int(numbers[i].split("-")[-1])
            assert (
                curr_num == prev_num + 1
            ), f"Numbers not sequential: {numbers[i-1]} → {numbers[i]}"


class TestTransliteration:
    """Тесты транслитерации кириллицы."""

    @pytest.mark.parametrize(
        "input_text,expected",
        [
            ("Москва", "Moskva"),
            ("Земляные работы", "Zemlyanye raboty"),
            ("СЧ-001", "SCh-001"),  # ← Ch, а не CH
            ("АКТ-2026-0001", "AKT-2026-0001"),
            ("Hello World", "Hello World"),  # Латиница не меняется
            ("", ""),  # Пустая строка
            ("Щука", "Schuka"),  # ← Sch, а не SCH
            ("щукa", "schuka"),  # ← строчные
        ],
    )
    def test_transliteration(self, input_text, expected):
        """Проверяем транслитерацию различных строк."""
        from app.services.pdf_service import _transliterate

        result = _transliterate(input_text)
        assert result == expected

    def test_transliteration_preserves_numbers(self):
        """Цифры и символы должны сохраняться."""
        from app.services.pdf_service import _transliterate

        result = _transliterate("INV-2026-0001")
        assert result == "INV-2026-0001"
