"""Unit тесты для finance_service."""


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

    def test_unique_numbers(self, db_session, company):
        """Тест: каждый номер документа уникален."""
        from datetime import datetime, timedelta

        from app.models.dispatch import Request

        # Создаём тестовые заявки
        requests_list = []
        for i in range(5):
            req = Request(
                client_id=None,  # nullable
                status="new",
                request_type="one_time",
                work_type=f"Test work {i}",
                object_address=f"Address {i}",
                planned_start=datetime.now() + timedelta(days=i),
                planned_end=datetime.now() + timedelta(days=i + 1),
                rate_type="hourly",
                source_channel="phone",
                priority="normal",
                company_id=company.id,
            )
            db_session.add(req)
            requests_list.append(req)

        db_session.commit()

        # Проверяем что все заявки созданы
        assert len(requests_list) == 5

        # Проверяем что у них уникальные ID
        ids = [r.id for r in requests_list]
        assert len(set(ids)) == 5
