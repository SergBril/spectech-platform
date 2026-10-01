"""Unit тесты для finance_service."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.company import Company
from app.models.dispatch import Request


class TestDocumentNumberGeneration:
    """Тесты генерации номеров документов."""

    def test_generate_invoice_number_format(self, db_session: Session):
        """Проверяем формат номера инвойса."""
        from app.services.finance_service import generate_document_number

        number = generate_document_number(db_session, "INV")

        assert number is not None
        assert number.startswith("INV-")
        parts = number.split("-")
        assert len(parts) == 3
        assert parts[0] == "INV"
        assert len(parts[1]) == 4  # Год
        assert parts[2].isdigit()  # Порядковый номер

    def test_generate_act_number_format(self, db_session: Session):
        """Проверяем формат номера акта."""
        from app.services.finance_service import generate_document_number

        number = generate_document_number(db_session, "ACT")

        assert number is not None
        assert number.startswith("ACT-")
        parts = number.split("-")
        assert len(parts) == 3
        assert parts[0] == "ACT"
        assert len(parts[1]) == 4
        assert parts[2].isdigit()

    def test_unique_numbers(
        self,
        db_session: Session,
        sample_company: Company,
        sample_contractor,
        sample_user: User,
    ):
        """Проверяем уникальность генерируемых номеров инвойсов."""
        from decimal import Decimal

        from app.models.finance import Invoice
        from app.services.finance_service import generate_document_number

        # Создаем базовую заявку (Request) для корректной привязки инвойсов (FOREIGN KEY)
        now = datetime.now()
        test_request = Request(
            client_id=sample_contractor.id,
            status="new",
            request_type="one_time",
            work_type="Test work for invoices",
            object_address="Test address",
            planned_start=now,
            planned_end=now + timedelta(days=1),
            source_channel="phone",
            priority="normal",
            company_id=sample_company.id,
            created_by=sample_user.id,
        )
        db_session.add(test_request)
        db_session.commit()
        db_session.refresh(test_request)

        numbers = []
        for i in range(5):
            num = generate_document_number(db_session, "INV")
            numbers.append(num)

            inv = Invoice(
                document_number=num,
                request_id=test_request.id,  # Исправлено: было request1.id
                client_id=sample_contractor.id,  # Исправлено: было client1.id
                company_id=sample_company.id,  # Исправлено: было company1.id
                subtotal=Decimal("1000.00"),
                vat_amount=Decimal("200.00"),
                total=Decimal("1200.00"),
                paid_amount=Decimal("0.00"),
                tax_system="osno",
                is_vat_included=True,
                status="draft",
                invoice_date=datetime.now(),
                due_date=datetime.now(),
            )
            db_session.add(inv)
            db_session.commit()

        assert len(set(numbers)) == 5

    def test_unique_requests_creation(
        self, db_session, sample_company, sample_user, sample_contractor
    ):
        """Проверяем, что можно создать несколько заявок и они получат уникальные ID."""
        from app.models.dispatch import Request

        now = datetime.now()
        created_requests = []

        for i in range(5):
            req = Request(
                client_id=sample_contractor.id,
                status="new",
                request_type="one_time",
                work_type=f"Test work {i}",
                object_address="Test address",
                planned_start=now,
                planned_end=now + timedelta(days=1),
                source_channel="phone",
                priority="normal",
                company_id=sample_company.id,
                created_by=sample_user.id,
            )
            db_session.add(req)
            db_session.flush()
            created_requests.append(req)

        db_session.commit()

        assert len(created_requests) == 5
        ids = [r.id for r in created_requests]
        assert len(set(ids)) == 5
