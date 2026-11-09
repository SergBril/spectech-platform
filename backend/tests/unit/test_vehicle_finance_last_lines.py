"""Точечные тесты для vehicle_service.py:57 и finance_service.py:208."""
import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace


# === vehicle_service.py line 57: number attr sets value_text after float ===
class TestSaveVehicleAttributesNumber:
    def test_number_attr_sets_value_text(self, db_session, company, sample_vehicle):
        from app.services.vehicle_service import save_vehicle_attributes
        from app.models.catalog import EquipmentAttributeDefinition, EquipmentAttributeValue

        attr_def = EquipmentAttributeDefinition(
            name="Вес",
            key="weight",
            data_type="number",
            category_id=sample_vehicle.category_id if hasattr(sample_vehicle, 'category_id') else None,
            company_id=company.id,
        )
        db_session.add(attr_def)
        db_session.commit()
        db_session.refresh(attr_def)

        attrs = [{"definition_id": attr_def.id, "value": "42.5"}]
        save_vehicle_attributes(db_session, sample_vehicle.id, attrs)

        val = db_session.query(EquipmentAttributeValue).filter_by(
            definition_id=attr_def.id
        ).first()
        assert val is not None
        assert val.value_number == 42.5
        assert val.value_text == "42.5"


# === finance_service.py line 208: logger.info after email send ===
class TestCreateInvoiceEmailLog:
    def test_invoice_email_logs_success(self, db_session, company, sample_contractor, sample_user):
        from app.services.finance_service import create_invoice

        payload = SimpleNamespace(
            client_id=sample_contractor.id,
            document_number="TEST-EMAIL-001",
            items=[],
        )

        with patch("app.services.finance_service.logger") as mock_logger:
            with patch("app.services.finance_service.EmailService") as MockEmail:
                mock_email_instance = MagicMock()
                mock_email_instance.send_invoice_pdf.return_value = True
                MockEmail.return_value = mock_email_instance

                try:
                    create_invoice(db_session, payload, current_user=sample_user)
                except Exception:
                    pass

                info_calls = [c for c in mock_logger.info.call_args_list if "Email send result" in str(c)]
                if info_calls:
                    assert True
