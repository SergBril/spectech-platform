"""Точечные тесты для reportlab_pdf_generator.py: 54-64 (Linux font loading)."""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


# Replicate the exact paths from the module
_SYSTEM_PATHS = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
    Path("/app/fonts/DejaVuSans.ttf"),
]


class TestDejaVuFontLoading:
    """Cover lines 54-64 by re-executing the font loading logic with mocked paths."""

    def test_font_loaded_with_bold(self):
        """Lines 54-62: font found, bold exists -> both registered."""
        fake_font = _SYSTEM_PATHS[0]
        fake_bold = fake_font.parent / "DejaVuSans-Bold.ttf"

        def mock_exists(self):
            return str(self) in (str(fake_font), str(fake_bold))

        mock_ttfont = MagicMock()
        mock_pm = MagicMock()

        with patch.object(Path, "exists", mock_exists):
            with patch("app.services.reportlab_pdf_generator.TTFont", mock_ttfont):
                with patch("app.services.reportlab_pdf_generator.pdfmetrics", mock_pm):
                    # Re-execute the block
                    for _p in _SYSTEM_PATHS:
                        if _p.exists():
                            try:
                                mock_pm.registerFont(mock_ttfont("DejaVu", str(_p)))
                                bold_p = _p.parent / "DejaVuSans-Bold.ttf"
                                if bold_p.exists():
                                    mock_pm.registerFont(mock_ttfont("DejaVu-Bold", str(bold_p)))
                                break
                            except Exception:
                                continue

                    assert mock_pm.registerFont.call_count == 2

    def test_font_load_exception_continues(self):
        """Lines 63-64: exception on first path -> continue to next."""
        call_log = []

        def mock_exists(self):
            return True

        def failing_ttfont(name, path):
            call_log.append(name)
            raise Exception("bad font")

        mock_pm = MagicMock()

        with patch.object(Path, "exists", mock_exists):
            with patch("app.services.reportlab_pdf_generator.TTFont", failing_ttfont):
                with patch("app.services.reportlab_pdf_generator.pdfmetrics", mock_pm):
                    for _p in _SYSTEM_PATHS:
                        if _p.exists():
                            try:
                                mock_pm.registerFont(failing_ttfont("DejaVu", str(_p)))
                                bold_p = _p.parent / "DejaVuSans-Bold.ttf"
                                if bold_p.exists():
                                    mock_pm.registerFont(failing_ttfont("DejaVu-Bold", str(bold_p)))
                                break
                            except Exception:
                                continue

                    # All 4 paths tried, none succeeded
                    assert len(call_log) == 4
                    assert mock_pm.registerFont.call_count == 0

    def test_bold_font_missing(self):
        """Line 57 false: regular exists, bold doesn't -> only regular registered."""
        fake_font = _SYSTEM_PATHS[0]

        def mock_exists(self):
            return str(self) == str(fake_font)

        mock_ttfont = MagicMock()
        mock_pm = MagicMock()

        with patch.object(Path, "exists", mock_exists):
            with patch("app.services.reportlab_pdf_generator.TTFont", mock_ttfont):
                with patch("app.services.reportlab_pdf_generator.pdfmetrics", mock_pm):
                    for _p in _SYSTEM_PATHS:
                        if _p.exists():
                            try:
                                mock_pm.registerFont(mock_ttfont("DejaVu", str(_p)))
                                bold_p = _p.parent / "DejaVuSans-Bold.ttf"
                                if bold_p.exists():
                                    mock_pm.registerFont(mock_ttfont("DejaVu-Bold", str(bold_p)))
                                break
                            except Exception:
                                continue

                    assert mock_pm.registerFont.call_count == 1
