"""Сервис генерации PDF-документов через WeasyPrint."""

import logging
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML

from app.services.translations import translate_unit

logger = logging.getLogger("spectech.pdf")

TEMPLATES_DIR = Path(__file__).parent / "email_templates"
env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

# 🆕 РЕГИСТРАЦИЯ ФИЛЬТРА ДЛЯ JINJA2
env.filters["translate_unit"] = translate_unit


def generate_act_pdf(act, request, contractor=None) -> bytes:
    """
    Генерирует PDF-акт из HTML-шаблона.
    """
    try:
        template = env.get_template("act_pdf.html")
        html_content = template.render(
            act=act,
            request=request,
            contractor=contractor,
        )

        pdf_bytes = HTML(string=html_content).write_pdf()

        logger.info(
            f"✅ PDF generated for act {act.document_number}: {len(pdf_bytes)} bytes"
        )
        return pdf_bytes

    except Exception as e:
        logger.error(f"❌ PDF generation failed for act {act.id}: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise


def _money_to_words_ru(amount: float) -> str:
    """Сумма прописью на русском (для ТОРГ-12)."""
    ones = [
        "",
        "один",
        "два",
        "три",
        "четыре",
        "пять",
        "шесть",
        "семь",
        "восемь",
        "девять",
        "десять",
        "одиннадцать",
        "двенадцать",
        "тринадцать",
        "четырнадцать",
        "пятнадцать",
        "шестнадцать",
        "семнадцать",
        "восемнадцать",
        "девятнадцать",
    ]
    fem = [
        "",
        "одна",
        "две",
        "три",
        "четыре",
        "пять",
        "шесть",
        "семь",
        "восемь",
        "девять",
    ]
    tens = [
        "",
        "",
        "двадцать",
        "тридцать",
        "сорок",
        "пятьдесят",
        "шестьдесят",
        "семьдесят",
        "восемьдесят",
        "девяносто",
    ]
    hund = [
        "",
        "сто",
        "двести",
        "триста",
        "четыреста",
        "пятьсот",
        "шестьсот",
        "семьсот",
        "восемьсот",
        "девятьсот",
    ]

    def three(n: int, feminine=False) -> str:
        out = []
        if n // 100:
            out.append(hund[n // 100])
        t = n % 100
        if t < 20:
            if t:
                out.append(fem[t] if (feminine and t < 10) else ones[t])
        else:
            out.append(tens[t // 10])
            if t % 10:
                out.append(fem[t % 10] if (feminine and t % 10 < 10) else ones[t % 10])
        return " ".join(out)

    def plural(n: int, forms: list) -> str:
        n = abs(n) % 100
        d = n % 10
        if 10 < n < 20:
            return forms[2]
        if 1 < d < 5:
            return forms[1]
        if d == 1:
            return forms[0]
        return forms[2]

    rub = int(amount)
    kop = int(round((amount - rub) * 100))
    parts = []
    mil, thou, rest = rub // 1_000_000, (rub % 1_000_000) // 1000, rub % 1000
    if mil:
        parts += [three(mil), plural(mil, ["миллион", "миллиона", "миллионов"])]
    if thou:
        parts += [
            three(thou, feminine=True),
            plural(thou, ["тысяча", "тысячи", "тысяч"]),
        ]
    if rest:
        parts.append(three(rest))
    if not parts:
        parts.append("ноль")
    parts.append(plural(rub, ["рубль", "рубля", "рублей"]))
    parts.append(f"{kop:02d} копеек")
    return " ".join(parts)


def generate_upd_pdf(act, company, client, request=None) -> bytes:
    """
    Генерирует PDF УПД (Универсальный передаточный документ) для акта.

    УПД = Акт + Счёт-фактура в одном документе (для ОСНО с НДС).
    Статус "1" = СЧФДОП (счёт-фактура + передаточный документ).
    Статус "2" = только передаточный документ (для УСН).
    """
    try:
        from datetime import date as date_type

        # Ставка НДС: для ОСНО по умолчанию 22% (ред. с 01.01.2026, ФЗ № 425-ФЗ)
        vat_rate_num = float(act.vat_rate or 0)
        if act.tax_system == "osno" and vat_rate_num <= 0:
            vat_rate_num = 22.0

        # Определяем статус УПД
        if act.tax_system == "osno" and vat_rate_num > 0:
            status = "1"  # СЧФДОП
        else:
            status = "2"  # Только передаточный документ

        # Безопасное получение bank_details
        def get_bank_field(obj, field_name):
            if not obj or not obj.bank_details:
                return ""
            if isinstance(obj.bank_details, dict):
                return obj.bank_details.get(field_name, "") or ""
            return ""

        # Описание работ (из заявки или акта)
        work_description = "Работы по акту"
        if request and request.work_type:
            work_description = request.work_type
        elif hasattr(act, "comment") and act.comment:
            work_description = act.comment

        # Дата документа
        doc_date = act.act_date or date_type.today()
        if isinstance(doc_date, str):
            doc_date = datetime.fromisoformat(doc_date.replace("Z", "+00:00"))

        # Дата создания акта (для основания)
        created_date_str = "—"
        if act.created_at:
            created_dt = act.created_at
            if isinstance(created_dt, str):
                created_dt = datetime.fromisoformat(created_dt.replace("Z", "+00:00"))
            created_date_str = created_dt.strftime("%d.%m.%Y")

        # 🆕 РАСЧЁТ СУММ (ПЕРЕД формированием контекста)
        total_amount = float(act.total_amount or 0)
        item_subtotal = total_amount
        item_vat = 0

        if act.tax_system == "osno" and vat_rate_num > 0:
            if getattr(act, "is_vat_included", True):
                item_subtotal = total_amount / (1 + vat_rate_num / 100)
                item_vat = total_amount - item_subtotal
            else:
                item_subtotal = total_amount
                item_vat = total_amount * vat_rate_num / 100
                total_amount = item_subtotal + item_vat

        # Формируем контекст для шаблона
        context = {
            "document_number": f"UPD-{act.document_number}",
            "document_date": doc_date.strftime("%d.%m.%Y"),
            "status": status,
            "show_vat": status == "1",
            "basis_document": f"Заявка №{act.request_id} от {created_date_str}",
            # Продавец (Исполнитель)
            "executor_name": company.name or "",
            "executor_inn": company.inn or "",
            "executor_kpp": getattr(company, "kpp", "") or "",
            "executor_address": company.legal_address or "",
            "executor_bank": get_bank_field(company, "bank_name"),
            "executor_account": get_bank_field(company, "account"),
            "executor_bik": get_bank_field(company, "bik"),
            "executor_correspondent_account": get_bank_field(
                company, "correspondent_account"
            ),
            # Покупатель (Заказчик)
            "client_name": client.name or "",
            "client_inn": client.inn or "",
            "client_kpp": getattr(client, "kpp", "") or "",
            "client_address": client.legal_address or "",
            "client_bank": get_bank_field(client, "bank_name"),
            "client_account": get_bank_field(client, "account"),
            "client_bik": get_bank_field(client, "bik"),
            "client_correspondent_account": get_bank_field(
                client, "correspondent_account"
            ),
            # Система налогообложения
            "tax_system": act.tax_system or "usn_6",
            "vat_rate": vat_rate_num,
            # Позиция (весь акт как одну услугу)
            "items": [
                {
                    "description": work_description,
                    "unit": "шт",
                    "quantity": 1,
                    "unit_price": item_subtotal,
                    "subtotal": item_subtotal,
                    "vat_amount": item_vat,
                    "total": item_subtotal + item_vat,
                }
            ],
            "subtotal": item_subtotal,
            "vat_amount": item_vat,
            "total_amount": item_subtotal + item_vat,
            # Даты и подписи
            "doc_day": doc_date.strftime("%d"),
            "doc_month": doc_date.strftime("%m"),
            "doc_year": doc_date.strftime("%Y"),
            "executor_position": getattr(company, "director_position", None)
            or "Генеральный директор",
            "client_position": "Генеральный директор",
            "sheets_count": 1,
        }

        # Рендерим HTML через общий Jinja2 (тот же env, что и для актов)
        template = env.get_template("upd_pdf.html")
        html_content = template.render(**context)

        # Генерируем PDF через WeasyPrint
        pdf_bytes = HTML(string=html_content).write_pdf()

        logger.info(
            f"✅ UPD PDF generated for act {act.document_number}: {len(pdf_bytes)} bytes"
        )
        return pdf_bytes

    except Exception as e:
        logger.error(f"❌ UPD PDF generation failed for act {act.id}: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise


def generate_torg12_pdf(
    act, company, client, request=None, driver_name=None, vehicle_plate=None
) -> bytes:
    """
    Генерирует PDF ТОРГ-12 (Расходная накладная) на основании акта.

    Используется для отгрузки товаров (песок, бетон, щебень, стройматериалы).
    Форма утверждена Постановлением Госкомстата РФ от 25.12.1998 № 132.
    """
    try:
        from datetime import date as date_type

        # Безопасное получение bank_details
        def get_bank_field(obj, field_name):
            if not obj or not obj.bank_details:
                return ""
            if isinstance(obj.bank_details, dict):
                return obj.bank_details.get(field_name, "") or ""
            return ""

        # Описание товаров/работ
        work_description = "Товар по накладной"
        if request and request.work_type:
            work_description = request.work_type
        elif hasattr(act, "comment") and act.comment:
            work_description = act.comment

        # Дата документа
        doc_date = act.act_date or date_type.today()
        if isinstance(doc_date, str):
            doc_date = datetime.fromisoformat(doc_date.replace("Z", "+00:00"))

        # Дата создания акта (для основания)
        created_date_str = "—"
        if act.created_at:
            created_dt = act.created_at
            if isinstance(created_dt, str):
                created_dt = datetime.fromisoformat(created_dt.replace("Z", "+00:00"))
            created_date_str = created_dt.strftime("%d.%m.%Y")

        # Метка системы налогообложения
        tax_system_labels = {
            "osno": "ОСНО",
            "usn_6": "УСН 6%",
            "usn_15": "УСН 15%",
            "patent": "Патент",
            "npd": "НПД",
        }
        tax_system_label = tax_system_labels.get(act.tax_system or "usn_6", "—")

        vat_rate_num = float(act.vat_rate or 0)
        if act.tax_system == "osno" and vat_rate_num <= 0:
            vat_rate_num = 22.0

        # 🆕 РАСЧЁТ СУММ (ПЕРЕД формированием контекста - ИСПРАВЛЕНО!)
        total_amount = float(act.total_amount or 0)
        item_subtotal = total_amount
        item_vat = 0

        if act.tax_system == "osno" and vat_rate_num > 0:
            if getattr(act, "is_vat_included", True):
                item_subtotal = total_amount / (1 + vat_rate_num / 100)
                item_vat = total_amount - item_subtotal
            else:
                item_subtotal = total_amount
                item_vat = total_amount * vat_rate_num / 100
                total_amount = item_subtotal + item_vat

        # Формируем контекст для шаблона (теперь item_subtotal и item_vat уже существуют)
        context = {
            "document_number": f"TORG-{act.document_number}",
            "document_date": doc_date.strftime("%d.%m.%Y"),
            "basis_document": f"Заявка №{act.request_id} от {created_date_str}",
            # Продавец (Исполнитель)
            "executor_name": company.name or "",
            "executor_inn": company.inn or "",
            "executor_kpp": getattr(company, "kpp", "") or "",
            "executor_address": company.legal_address or "",
            "executor_bank": get_bank_field(company, "bank_name"),
            "executor_account": get_bank_field(company, "account"),
            "executor_bik": get_bank_field(company, "bik"),
            "executor_correspondent_account": get_bank_field(
                company, "correspondent_account"
            ),
            # Покупатель (Заказчик)
            "client_name": client.name or "",
            "client_inn": client.inn or "",
            "client_kpp": getattr(client, "kpp", "") or "",
            "client_address": client.legal_address or "",
            "client_bank": get_bank_field(client, "bank_name"),
            "client_account": get_bank_field(client, "account"),
            "client_bik": get_bank_field(client, "bik"),
            "client_correspondent_account": get_bank_field(
                client, "correspondent_account"
            ),
            # Система налогообложения
            "tax_system": act.tax_system or "usn_6",
            "tax_system_label": tax_system_label,
            "vat_rate": vat_rate_num,
            "show_vat": (act.tax_system == "osno" and vat_rate_num > 0),
            # Водитель и машина
            "driver_name": driver_name or "",
            "vehicle_plate": vehicle_plate or "",
            # Позиция (одна позиция для первой версии)
            "items": [
                {
                    "description": work_description,
                    "unit": "шт",
                    "quantity": 1,
                    "unit_price": item_subtotal,
                    "subtotal": item_subtotal,
                    "vat_amount": item_vat,
                    "total": item_subtotal + item_vat,
                }
            ],
            "subtotal": item_subtotal,
            "vat_amount": item_vat,
            "total_amount": item_subtotal + item_vat,
            # Сумма прописью (теперь item_subtotal и item_vat уже рассчитаны!)
            "total_in_words": _money_to_words_ru(item_subtotal + item_vat),
            "total_quantity": 1,
            "executor_position": getattr(company, "director_position", None)
            or "Генеральный директор",
            "client_position": "Генеральный директор",
        }

        # Рендерим HTML
        template = env.get_template("torg12_pdf.html")
        html_content = template.render(**context)

        # Генерируем PDF
        pdf_bytes = HTML(string=html_content).write_pdf()

        logger.info(
            f"✅ TORG-12 PDF generated for act {act.document_number}: {len(pdf_bytes)} bytes"
        )
        return pdf_bytes

    except Exception as e:
        logger.error(f"❌ TORG-12 PDF generation failed for act {act.id}: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise


def generate_invoice_pdf(invoice, contractor=None) -> bytes:
    """
    Генерирует PDF-счёт из HTML-шаблона.
    """
    try:
        template = env.get_template("invoice_pdf.html")
        html_content = template.render(
            invoice=invoice,
            contractor=contractor,
        )

        pdf_bytes = HTML(string=html_content).write_pdf()

        logger.info(
            f"✅ Invoice PDF generated: {invoice.document_number}: {len(pdf_bytes)} bytes"
        )
        return pdf_bytes

    except Exception as e:
        logger.error(f"❌ Invoice PDF generation failed for {invoice.id}: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise


def generate_invoice_facture_pdf(act, request, contractor=None) -> bytes:
    """
    Генерирует PDF счёт-фактуры на основании акта.
    Вызывается только для ОСНО с НДС.
    """
    try:
        from datetime import date
        from decimal import Decimal

        template = env.get_template("invoice_facture_pdf.html")

        # Расчёт суммы без НДС
        total_amount = Decimal(str(act.total_amount or 0))
        vat_amount = Decimal(str(act.vat_amount or 0))
        vat_rate = Decimal(str(act.vat_rate or 22))
        total_without_vat = total_amount - vat_amount

        # Номер счёт-фактуры (на основе акта)
        facture_number = act.document_number.replace("ACT", "SF")
        facture_date = act.act_date or date.today()

        html_content = template.render(
            act=act,
            request=request,
            contractor=contractor,
            facture_number=facture_number,
            facture_date=facture_date,
            vat_rate=vat_rate,
            total_without_vat=total_without_vat,
        )

        pdf_bytes = HTML(string=html_content).write_pdf()

        logger.info(
            f"✅ Invoice facture PDF generated for act {act.document_number}: {len(pdf_bytes)} bytes"
        )
        return pdf_bytes

    except Exception as e:
        logger.error(f"❌ Invoice facture PDF generation failed for act {act.id}: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise
