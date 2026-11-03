"""Unit tests for MAX Messenger notification templates."""


class TestNotificationTemplates:
    """Tests for all MaxNotificationTemplates static methods."""

    def test_request_created(self):
        from app.services.max_messenger_service import MaxNotificationTemplates as NT

        title, body = NT.request_created(
            42, "Земляные работы", "Москва, ул. Тест", "01.12.2026 08:00"
        )
        assert "заявка" in title.lower()
        assert "#42" in body
        assert "Земляные работы" in body
        assert "Москва" in body

    def test_offer_received(self):
        from app.services.max_messenger_service import MaxNotificationTemplates as NT

        title, body = NT.offer_received(42, "OOO Test", 15000.0, "CAT 320")
        assert "отклик" in title.lower()
        assert "#42" in body
        assert "OOO Test" in body
        assert "CAT 320" in body
        assert "15,000" in body

    def test_payment_received(self):
        from app.services.max_messenger_service import MaxNotificationTemplates as NT

        title, body = NT.payment_received("INV-001", 50000.0, "OOO Payer")
        assert "оплат" in title.lower()
        assert "INV-001" in body
        assert "50,000" in body
        assert "OOO Payer" in body

    def test_shift_completed(self):
        from app.services.max_messenger_service import MaxNotificationTemplates as NT

        title, body = NT.shift_completed(10, "Экскаватор CAT", "01.12.2026", 8.5)
        assert "смен" in title.lower() or "заверш" in title.lower()
        assert "CAT" in body
        assert "8.5" in body

    def test_salary_approved(self):
        from app.services.max_messenger_service import MaxNotificationTemplates as NT

        title, body = NT.salary_approved(5, "Ivanov I.I.", 75000.0, "November 2026")
        assert "зарплат" in title.lower()
        assert "Ivanov" in body
        assert "75,000" in body
        assert "November 2026" in body

    def test_geofence_alert(self):
        from app.services.max_messenger_service import MaxNotificationTemplates as NT

        title, body = NT.geofence_alert(
            "KAMAZ-001", "Object 5", "exit", "01.12.2026 14:30"
        )
        assert "геозон" in title.lower()
        assert "KAMAZ-001" in body
        assert "01.12.2026" in body

    def test_maintenance_due(self):
        from app.services.max_messenger_service import MaxNotificationTemplates as NT

        title, body = NT.maintenance_due("Экскаватор CAT 320", 260.0, 250.0, 10.0)
        assert "ТО" in title
        assert "CAT 320" in body
        assert "260" in body
        assert "10" in body

    def test_engine_hours_warning(self):
        from app.services.max_messenger_service import MaxNotificationTemplates as NT

        title, body = NT.engine_hours_warning("Бульдозер D6", 12.5, 10.0)
        assert "моточас" in title.lower() or "превышение" in title.lower()
        assert "D6" in body
        assert "12.5" in body

    def test_sync_error(self):
        from app.services.max_messenger_service import MaxNotificationTemplates as NT

        title, body = NT.sync_error("wialon", "Connection timeout after 30s", 5)
        assert "wialon" in body
        assert "timeout" in body.lower()
        assert "5" in body

    def test_all_templates_return_tuple(self):
        """Все шаблоны возвращают кортеж (title, body)."""
        from app.services.max_messenger_service import MaxNotificationTemplates as NT

        templates = [
            NT.request_created(1, "test", "addr", "01.01"),
            NT.offer_received(1, "co", 100.0, "veh"),
            NT.payment_received("inv", 100.0, "payer"),
            NT.shift_completed(1, "veh", "01.01", 8.0),
            NT.salary_approved(1, "emp", 50000.0, "period"),
            NT.geofence_alert("veh", "geo", "exit", "01.01"),
            NT.maintenance_due("veh", 260.0, 250.0, 10.0),
            NT.engine_hours_warning("veh", 12.0, 10.0),
            NT.sync_error("prov", "err", 3),
        ]

        for t in templates:
            assert isinstance(t, tuple), f"Template should return tuple, got {type(t)}"
            assert (
                len(t) == 2
            ), f"Template should return (title, body), got {len(t)} elements"
            assert isinstance(t[0], str) and len(t[0]) > 0
            assert isinstance(t[1], str) and len(t[1]) > 0
