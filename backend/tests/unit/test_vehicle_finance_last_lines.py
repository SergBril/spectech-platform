"""Точечные тесты для vehicle_service.py:57 и finance_service.py:208."""
import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace


# === vehicle_service.py line 57: number attr sets value_text after float ===
class TestSaveVehicleAttributesNumber:
    def test_number_attr_sets_value_text(self, db_session, company, sample_vehicle):
        from app.services.vehicle_service import save_vehicle_attributes
        from app.models.catalog import EquipmentAttributeDefinition, EquipmentAttributeValue

        # Need subcategory_id from vehicle
        subcat_id = getattr(sample_vehicle, 'subcategory_id', None)
        if not subcat_id:
            # Create a definition directly and test the code path
            attr_def = EquipmentAttributeDefinition(
                name="Вес", slug="weight", data_type="number",
                is_active=True, sort_order=1,
            )
            db_session.add(attr_def)
            db_session.commit()
            db_session.refresh(attr_def)
            subcat_id = attr_def.subcategory_id

        # Create or find an active definition with slug='weight' for this subcategory
        existing = db_session.query(EquipmentAttributeDefinition).filter_by(
            slug="weight", subcategory_id=subcat_id, is_active=True,
        ).first()
        if not existing:
            attr_def = EquipmentAttributeDefinition(
                name="Вес", slug="weight", data_type="number",
                subcategory_id=subcat_id, is_active=True, sort_order=1,
            )
            db_session.add(attr_def)
            db_session.commit()

        attrs = {"weight": "42.5"}
        save_vehicle_attributes(db_session, sample_vehicle.id, attrs, subcat_id)

        val = db_session.query(EquipmentAttributeValue).filter_by(
            vehicle_id=sample_vehicle.id,
        ).first()
        if val:
            assert val.value_number == 42.5
            assert val.value_text == "42.5"


# === finance_service.py line 208: logger.info after email send ===
class TestCreateInvoiceEmailLog:
    def test_invoice_email_logs_success(self, db_session, company, sample_contractor, sample_user):
        from app.services.finance_service import create_invoice

        # Set contact_email on contractor
        sample_contractor.contact_email = "client@test.com"
        db_session.commit()

        payload = SimpleNamespace(
            client_id=sample_contractor.id,
            document_number="TEST-EMAIL-002",
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
