"""Coverage tests for reportlab_pdf_generator."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace


class TestMoneyToWordsRu:
    """Cover _money_to_words_ru (lines 69-128)."""

    def test_zero(self):
        from app.services.reportlab_pdf_generator import _money_to_words_ru

        result = _money_to_words_ru(0)
        assert "ноль" in result
        assert "00 копеек" in result

    def test_simple_amount(self):
        from app.services.reportlab_pdf_generator import _money_to_words_ru

        result = _money_to_words_ru(1500.50)
        assert "тысяч" in result
        assert "пятьсот" in result
        assert "50 копеек" in result

    def test_millions(self):
        from app.services.reportlab_pdf_generator import _money_to_words_ru

        result = _money_to_words_ru(2_500_000.00)
        assert "миллион" in result

    def test_feminine_thousands(self):
        from app.services.reportlab_pdf_generator import _money_to_words_ru

        result = _money_to_words_ru(1000.00)
        assert "тысяч" in result


class TestCalc:
    """Cover _calc (lines 195-210)."""

    def test_osno_with_vat(self):
        from app.services.reportlab_pdf_generator import _calc

        act = SimpleNamespace(
            vat_rate=Decimal("20"), tax_system="osno", total_amount=Decimal("120")
        )
        vat_rate, show_vat, subtotal, vat, total, status = _calc(act)
        assert show_vat is True
        assert status == "1"
        assert abs(subtotal - 100.0) < 0.01
        assert abs(vat - 20.0) < 0.01

    def test_osno_no_vat_rate(self):
        from app.services.reportlab_pdf_generator import _calc

        act = SimpleNamespace(
            vat_rate=Decimal("0"), tax_system="osno", total_amount=Decimal("122")
        )
        vat_rate, show_vat, subtotal, vat, total, status = _calc(act)
        assert vat_rate == 22.0

    def test_usn(self):
        from app.services.reportlab_pdf_generator import _calc

        act = SimpleNamespace(
            vat_rate=Decimal("0"), tax_system="usn", total_amount=Decimal("100")
        )
        vat_rate, show_vat, subtotal, vat, total, status = _calc(act)
        assert show_vat is False
        assert status == "2"
        assert vat == 0.0


class TestNumAndQty:
    """Cover _num and _qty (lines 211-219)."""

    def test_num(self):
        from app.services.reportlab_pdf_generator import _num

        assert _num(62900.01) == "62 900.01"

    def test_qty(self):
        from app.services.reportlab_pdf_generator import _qty

        result = _qty(1.5)
        assert "," in result  # Russian decimal separator


class TestStyles:
    """Cover _styles (lines 175-193)."""

    def test_returns_styles(self):
        from app.services.reportlab_pdf_generator import _styles

        styles = _styles()
        assert (
            "RuBody" in [s.name for s in styles.byName.values()] or "RuBody" in styles
        )


class TestGenerateUpdReportlab:
    """Cover generate_upd_reportlab (lines 303-624)."""

    def test_generates_bytes(self):
        from app.services.reportlab_pdf_generator import generate_upd_reportlab

        act = SimpleNamespace(
            document_number="ACT-2026-0001",
            act_date=date(2026, 11, 5),
            request_id=1,
            vat_rate=Decimal("20"),
            tax_system="osno",
            total_amount=Decimal("12000"),
        )
        company = SimpleNamespace(
            name="ООО Продавец",
            inn="1234567890",
            kpp="123456789",
            legal_address="Москва",
        )
        client = SimpleNamespace(
            name="ООО Покупатель",
            inn="0987654321",
            kpp="987654321",
            legal_address="СПб",
        )
        request = SimpleNamespace(work_type="earthworks")

        result = generate_upd_reportlab(act, company, client, request=request)
        assert isinstance(result, bytes)
        assert len(result) > 100
        assert result[:5] == b"%PDF-"

    def test_without_items(self):
        from app.services.reportlab_pdf_generator import generate_upd_reportlab

        act = SimpleNamespace(
            document_number="ACT-2026-0002",
            act_date=date(2026, 11, 5),
            request_id=None,
            vat_rate=Decimal("0"),
            tax_system="usn",
            total_amount=Decimal("5000"),
        )
        company = SimpleNamespace(name="ИП Тест", inn="123", kpp="", legal_address="-")
        client = SimpleNamespace(
            name="ООО Клиент", inn="456", kpp="", legal_address="-"
        )

        result = generate_upd_reportlab(act, company, client)
        assert isinstance(result, bytes)
        assert len(result) > 100


class TestGenerateTorg12Reportlab:
    """Cover generate_torg12_reportlab (lines 626-end)."""

    def test_generates_bytes(self):
        from app.services.reportlab_pdf_generator import generate_torg12_reportlab

        act = SimpleNamespace(
            document_number="ACT-2026-0003",
            act_date=date(2026, 11, 5),
            request_id=1,
            vat_rate=Decimal("20"),
            tax_system="osno",
            total_amount=Decimal("12000"),
        )
        company = SimpleNamespace(
            name="ООО Продавец",
            inn="1234567890",
            kpp="123456789",
            legal_address="Москва",
            bank_details={"bank_name": "Сбер"},
        )
        client = SimpleNamespace(
            name="ООО Покупатель",
            inn="0987654321",
            kpp="987654321",
            legal_address="СПб",
            bank_details={"bank_name": "ВТБ"},
        )
        request = SimpleNamespace(work_type="crane")

        result = generate_torg12_reportlab(
            act,
            company,
            client,
            request=request,
            driver_name="Иванов",
            vehicle_plate="А123АА",
        )
        assert isinstance(result, bytes)
        assert len(result) > 100
        assert result[:5] == b"%PDF-"

    def test_without_optional_params(self):
        from app.services.reportlab_pdf_generator import generate_torg12_reportlab

        act = SimpleNamespace(
            document_number="ACT-2026-0004",
            act_date=date(2026, 11, 5),
            request_id=None,
            vat_rate=Decimal("0"),
            tax_system="usn",
            total_amount=Decimal("5000"),
        )
        company = SimpleNamespace(
            name="ИП Тест", inn="123", kpp="", legal_address="-", bank_details=None
        )
        client = SimpleNamespace(
            name="ООО Клиент", inn="456", kpp="", legal_address="-", bank_details=None
        )

        result = generate_torg12_reportlab(act, company, client)
        assert isinstance(result, bytes)
