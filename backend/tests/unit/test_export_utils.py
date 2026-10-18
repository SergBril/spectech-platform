"""Unit-тесты утилит экспорта заявок (PDF/Excel)."""

from datetime import UTC, datetime

from app.utils.export_utils import (
    _fmt_dt,
    _prepare_rows,
    export_requests_excel,
    export_requests_pdf,
)


class TestFormatDatetime:
    """Тесты форматирования дат."""

    def test_none_returns_empty(self):
        assert _fmt_dt(None) == ""

    def test_iso_string(self):
        result = _fmt_dt("2026-10-17T14:30:00Z")
        assert "17.10.2026" in result
        assert "14:30" in result

    def test_datetime_object(self):
        dt = datetime(2026, 10, 17, 14, 30, tzinfo=UTC)
        result = _fmt_dt(dt)
        assert "17.10.2026" in result

    def test_invalid_string(self):
        result = _fmt_dt("not-a-date")
        assert isinstance(result, str)


class TestPrepareRows:
    """Тесты подготовки строк из данных заявок."""

    def test_dict_input(self):
        data = [
            {
                "id": 1,
                "work_type": "Земляные работы",
                "object_address": "Москва, ул. Тестовая",
                "planned_start": "2026-10-17T09:00:00Z",
                "planned_end": "2026-10-18T09:00:00Z",
                "status": "new",
                "priority": "high",
                "estimated_amount": 150000,
                "vehicle_category_name": "Экскаваторы",
                "assigned_vehicle_name": "CAT 320D",
                "client_name": "ООО Тест",
            }
        ]
        rows = _prepare_rows(data)
        assert len(rows) == 1
        assert rows[0]["id"] == "1"
        assert rows[0]["work_type"] == "Земляные работы"
        assert rows[0]["status_label"] == "Новая"
        assert rows[0]["priority_label"] == "Высокий"
        assert "150,000" in rows[0]["amount"]

    def test_missing_fields_default_to_dash(self):
        data = [{"id": 1}]
        rows = _prepare_rows(data)
        assert rows[0]["work_type"] == "-"
        assert rows[0]["object_address"] == "-"
        assert rows[0]["vehicle_category_name"] == "-"

    def test_empty_list(self):
        assert _prepare_rows([]) == []

    def test_period_formatting(self):
        data = [
            {
                "id": 1,
                "planned_start": "2026-10-17T09:00:00Z",
                "planned_end": "2026-10-18T18:00:00Z",
            }
        ]
        rows = _prepare_rows(data)
        assert " - " in rows[0]["period"]


class TestExportRequestsPdf:
    """Тесты генерации PDF."""

    def test_generates_valid_pdf(self):
        data = [
            {
                "id": 1,
                "work_type": "Тестовая работа",
                "object_address": "Москва",
                "status": "new",
                "priority": "normal",
            }
        ]
        pdf_bytes = export_requests_pdf(data, title="Тест")
        assert isinstance(pdf_bytes, bytes | bytearray)
        assert len(pdf_bytes) > 0
        # PDF должен начинаться с %PDF
        assert pdf_bytes[:5] == b"%PDF-"

    def test_empty_data_generates_pdf(self):
        pdf_bytes = export_requests_pdf([], title="Пусто")
        assert isinstance(pdf_bytes, bytes | bytearray)
        assert len(pdf_bytes) > 0

    def test_cyrillic_content(self):
        data = [
            {
                "id": 1,
                "work_type": "Рытьё котлована",
                "object_address": "Москва, ул. Строителей",
                "status": "completed",
                "priority": "urgent",
                "vehicle_category_name": "Экскаваторы гусеничные",
            }
        ]
        pdf_bytes = export_requests_pdf(data, title="Заявки на земляные работы")
        assert len(pdf_bytes) > 100


class TestExportRequestsExcel:
    """Тесты генерации Excel."""

    def test_generates_valid_xlsx(self):
        data = [
            {
                "id": 1,
                "work_type": "Тестовая работа",
                "object_address": "Москва",
                "status": "new",
                "priority": "normal",
            }
        ]
        xlsx_bytes = export_requests_excel(data, title="Тест")
        assert isinstance(xlsx_bytes, bytes)
        assert len(xlsx_bytes) > 0
        # XLSX начинается с PK (ZIP signature)
        assert xlsx_bytes[:2] == b"PK"

    def test_empty_data_generates_xlsx(self):
        xlsx_bytes = export_requests_excel([], title="Пусто")
        assert isinstance(xlsx_bytes, bytes)
        assert len(xlsx_bytes) > 0

    def test_multiple_rows(self):
        data = [
            {"id": i, "work_type": f"Работа {i}", "status": "new", "priority": "normal"}
            for i in range(10)
        ]
        xlsx_bytes = export_requests_excel(data, title="Много заявок")
        assert len(xlsx_bytes) > 1000
