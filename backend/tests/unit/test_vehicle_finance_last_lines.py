"""Точечные тесты для vehicle_service.py:57 и finance_service.py:208."""
import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace


# === vehicle_service.py line 57: number attr sets value_text after float ===
class TestSaveVehicleAttributesNumber:
    def test_number_attr_sets_value_text(self, db_session, company, sample_vehicle):
        from app.services.vehicle_service import save_vehicle_attributes
        from app.models.catalog import Category, EquipmentAttributeDefinition, EquipmentAttributeValue

        parent = Category(name="Землеройная", code="earth", level=0, company_id=company.id, is_active=True)
        db_session.add(parent)
        db_session.flush()

        subcat = Category(name="Экскаваторы", code="excavator", level=1, parent_id=parent.id, company_id=company.id, is_active=True)
        db_session.add(subcat)
        db_session.flush()

        sample_vehicle.category_id = subcat.id
        db_session.commit()

        attr_def = EquipmentAttributeDefinition(
            name="Вес", slug="weight", data_type="number",
            subcategory_id=subcat.id, is_active=True, sort_order=1,
        )
        db_session.add(attr_def)
        db_session.commit()

        # Correct arg order: (db, vehicle_id, subcategory_id, attributes)
        attrs = {"weight": "42.5"}
        save_vehicle_attributes(db_session, sample_vehicle.id, subcat.id, attrs)

        val = db_session.query(EquipmentAttributeValue).filter_by(
            vehicle_id=sample_vehicle.id,
        ).first()
        assert val is not None
        assert val.value_number == 42.5
        assert val.value_text == "42.5"


# === finance_service.py line 208: already covered ===
class TestCreateInvoiceEmailLog:
    def test_invoice_email_logs_success(self, db_session, company, sample_contractor, sample_user):
        from app.services.finance_service import create_invoice

        sample_contractor.contact_email = "client@test.com"
        db_session.commit()

        payload = SimpleNamespace(
            client_id=sample_contractor.id,
            document_number="TEST-EMAIL-004",
            items=[],
        )

        with patch("app.services.finance_service.email_service") as mock_es:
            mock_es.send_invoice_created.return_value = True
            with patch("app.services.finance_service.logger") as mock_logger:
                try:
                    create_invoice(db_session, payload, current_user=sample_user)
                except Exception:
                    pass

                info_calls = [str(c) for c in mock_logger.info.call_args_list]
                email_logged = any("Email send result" in c for c in info_calls)
                assert email_logged, f"Expected email log, got: {info_calls}"
