"""Обёртки для вызова ReportLab генераторов."""

from app.services.reportlab_pdf_generator import (
    generate_torg12_reportlab,
    generate_upd_reportlab,
)


def fill_upd_pdf(act, company, client, request=None) -> bytes:
    """Заполняет PDF УПД через ReportLab."""
    return generate_upd_reportlab(act, company, client, request)


def fill_torg12_pdf(
    act, company, client, request=None, driver_name=None, vehicle_plate=None
) -> bytes:
    """Заполняет PDF ТОРГ-12 через ReportLab."""
    return generate_torg12_reportlab(
        act, company, client, request, driver_name, vehicle_plate
    )
