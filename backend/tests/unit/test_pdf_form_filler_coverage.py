"""Coverage tests for pdf_form_filler."""
from unittest.mock import MagicMock, patch


class TestFillUpdPdf:
    """Cover fill_upd_pdf (lines 9-11)."""

    def test_delegates_to_generator(self):
        from app.services.pdf_form_filler import fill_upd_pdf
        act = MagicMock()
        company = MagicMock()
        client = MagicMock()
        request = MagicMock()
        with patch("app.services.pdf_form_filler.generate_upd_reportlab", return_value=b"pdf") as mock_gen:
            result = fill_upd_pdf(act, company, client, request)
        assert result == b"pdf"
        mock_gen.assert_called_once_with(act, company, client, request)

    def test_without_request(self):
        from app.services.pdf_form_filler import fill_upd_pdf
        with patch("app.services.pdf_form_filler.generate_upd_reportlab", return_value=b"pdf") as mock_gen:
            result = fill_upd_pdf(MagicMock(), MagicMock(), MagicMock())
        assert result == b"pdf"
        mock_gen.assert_called_once()


class TestFillTorg12Pdf:
    """Cover fill_torg12_pdf (lines 14-20)."""

    def test_delegates_with_all_args(self):
        from app.services.pdf_form_filler import fill_torg12_pdf
        act = MagicMock()
        company = MagicMock()
        client = MagicMock()
        request = MagicMock()
        with patch("app.services.pdf_form_filler.generate_torg12_reportlab", return_value=b"pdf") as mock_gen:
            result = fill_torg12_pdf(act, company, client, request, "Ivanov", "A123BC")
        assert result == b"pdf"
        mock_gen.assert_called_once_with(act, company, client, request, "Ivanov", "A123BC")

    def test_without_optional_args(self):
        from app.services.pdf_form_filler import fill_torg12_pdf
        with patch("app.services.pdf_form_filler.generate_torg12_reportlab", return_value=b"pdf") as mock_gen:
            result = fill_torg12_pdf(MagicMock(), MagicMock(), MagicMock())
        assert result == b"pdf"
        mock_gen.assert_called_once()
