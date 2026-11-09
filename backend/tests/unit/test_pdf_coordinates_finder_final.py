"""Comprehensive tests for pdf_coordinates_finder -> 100%."""

from unittest.mock import MagicMock, patch, mock_open

import pytest

from app.services.pdf_coordinates_finder import create_coordinate_finder_pdf


class TestCreateCoordinateFinderPdf:
    def test_basic(self):
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.rect.width = 60
        mock_page.rect.height = 60
        mock_shape = MagicMock()
        mock_page.new_shape.return_value = mock_shape
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))
        mock_doc.__enter__ = MagicMock(return_value=mock_doc)
        mock_doc.__exit__ = MagicMock(return_value=False)

        with patch("app.services.pdf_coordinates_finder.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            mock_fitz.Point = MagicMock(side_effect=lambda x, y: (x, y))
            with patch("app.services.pdf_coordinates_finder.tempfile.NamedTemporaryFile") as tmp:
                tmp.return_value.name = "/tmp/test_grid.pdf"
                tmp.return_value.__enter__ = MagicMock(return_value=tmp.return_value)
                tmp.return_value.__exit__ = MagicMock(return_value=False)
                with patch("app.services.pdf_coordinates_finder.webbrowser.open") as wb:
                    result = create_coordinate_finder_pdf("/fake/source.pdf")
        assert result == "/tmp/test_grid.pdf"
        mock_doc.save.assert_called_once()
        mock_doc.close.assert_called_once()
        wb.assert_called_once()

    def test_multiple_pages(self):
        mock_doc = MagicMock()
        page1 = MagicMock()
        page1.rect.width = 30
        page1.rect.height = 30
        page2 = MagicMock()
        page2.rect.width = 90
        page2.rect.height = 90
        mock_shape = MagicMock()
        page1.new_shape.return_value = mock_shape
        page2.new_shape.return_value = mock_shape
        mock_doc.__iter__ = MagicMock(return_value=iter([page1, page2]))

        with patch("app.services.pdf_coordinates_finder.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            mock_fitz.Point = MagicMock(side_effect=lambda x, y: (x, y))
            with patch("app.services.pdf_coordinates_finder.tempfile.NamedTemporaryFile") as tmp:
                tmp.return_value.name = "/tmp/multi.pdf"
                with patch("app.services.pdf_coordinates_finder.webbrowser.open"):
                    result = create_coordinate_finder_pdf("/fake/source.pdf")
        assert result == "/tmp/multi.pdf"
        # Both pages should have shapes drawn
        assert page1.new_shape.call_count >= 1
        assert page2.new_shape.call_count >= 1

    def test_zero_dimensions(self):
        """Edge case: page with zero dimensions."""
        mock_doc = MagicMock()
        mock_page = MagicMock()
        mock_page.rect.width = 0
        mock_page.rect.height = 0
        mock_doc.__iter__ = MagicMock(return_value=iter([mock_page]))

        with patch("app.services.pdf_coordinates_finder.fitz") as mock_fitz:
            mock_fitz.open.return_value = mock_doc
            mock_fitz.Point = MagicMock(side_effect=lambda x, y: (x, y))
            with patch("app.services.pdf_coordinates_finder.tempfile.NamedTemporaryFile") as tmp:
                tmp.return_value.name = "/tmp/zero.pdf"
                with patch("app.services.pdf_coordinates_finder.webbrowser.open"):
                    result = create_coordinate_finder_pdf("/fake/source.pdf")
        assert result == "/tmp/zero.pdf"



class TestMainBlock:
    def test_main_with_args(self):
        """Cover if __name__ == '__main__' with valid args."""
        import runpy
        from unittest.mock import patch
        with patch("app.services.pdf_coordinates_finder.create_coordinate_finder_pdf") as mock_fn:
            with patch("sys.argv", ["pdf_coordinates_finder.py", "/fake/path.pdf"]):
                runpy.run_module("app.services.pdf_coordinates_finder", run_name="__main__")
            mock_fn.assert_called_once_with("/fake/path.pdf")

    def test_main_no_args(self):
        """Cover sys.exit(1) when no args provided."""
        import runpy
        with patch("sys.argv", ["pdf_coordinates_finder.py"]):
            with pytest.raises(SystemExit) as exc_info:
                runpy.run_module("app.services.pdf_coordinates_finder", run_name="__main__")
            assert exc_info.value.code == 1
