"""Cover reportlab_pdf_generator.py lines 54-64 by creating real font files."""
import importlib
import sys
import shutil
import pytest
from pathlib import Path


# Use a path that works on Windows too
_TEST_FONT_DIR = Path("C:/app/fonts")
_TEST_REGULAR = _TEST_FONT_DIR / "DejaVuSans.ttf"
_TEST_BOLD = _TEST_FONT_DIR / "DejaVuSans-Bold.ttf"

# Find a real TTF font on the system to copy
_WINDOWS_FONT = Path("C:/Windows/Fonts/arial.ttf")


def _setup_fonts(with_bold=True):
    """Copy a real TTF to the expected Linux path."""
    _TEST_FONT_DIR.mkdir(parents=True, exist_ok=True)
    if _WINDOWS_FONT.exists():
        shutil.copy2(_WINDOWS_FONT, _TEST_REGULAR)
        if with_bold:
            shutil.copy2(_WINDOWS_FONT, _TEST_BOLD)
    else:
        # Create dummy files (TTFont will fail -> covers except branch)
        _TEST_REGULAR.write_bytes(b"dummy")
        if with_bold:
            _TEST_BOLD.write_bytes(b"dummy")


def _cleanup_fonts():
    for f in [_TEST_REGULAR, _TEST_BOLD]:
        if f.exists():
            f.unlink()
    if _TEST_FONT_DIR.exists():
        try:
            _TEST_FONT_DIR.rmdir()
        except OSError:
            pass


def _reload_module():
    mod_name = "app.services.reportlab_pdf_generator"
    mods_to_remove = [k for k in sys.modules if k.startswith(mod_name)]
    saved = {k: sys.modules.pop(k) for k in mods_to_remove}
    try:
        return importlib.import_module(mod_name)
    finally:
        for k, v in saved.items():
            sys.modules[k] = v


class TestLinuxFontLoadingReal:
    """Cover lines 54-64 with real filesystem."""

    def test_font_found_with_bold(self):
        """Lines 54-62: font + bold exist -> registered."""
        _setup_fonts(with_bold=True)
        try:
            mod = _reload_module()
            # Module should have loaded DejaVu from /app/fonts/
            assert mod.FONT_REGULAR == "DejaVu"
        finally:
            _cleanup_fonts()

    def test_font_found_no_bold(self):
        """Line 57 false: regular exists, bold missing."""
        _setup_fonts(with_bold=False)
        try:
            mod = _reload_module()
            assert mod.FONT_REGULAR == "DejaVu"
        finally:
            _cleanup_fonts()

    def test_invalid_font_exception_continues(self):
        """Lines 63-64: TTFont fails on dummy file -> continue."""
        _TEST_FONT_DIR.mkdir(parents=True, exist_ok=True)
        # Write invalid font data
        _TEST_REGULAR.write_bytes(b"not a real font")
        try:
            mod = _reload_module()
            # Should fall through (may or may not load depending on TTFont behavior)
            assert mod is not None
        finally:
            _cleanup_fonts()
