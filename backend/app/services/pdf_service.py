"""Сервис генерации PDF документов на русском языке."""

from datetime import datetime

# === СЛОВАРЬ ПЕРЕВОДА ЕДИНИЦ ИЗМЕРЕНИЯ ===
UNIT_TRANSLATIONS = {
    "hourly": "час",
    "hour": "час",
    "hr": "час",
    "shift": "смена",
    "smena": "смена",
    "km": "км",
    "fixed": "услуга",
    "service": "услуга",
    "usluga": "услуга",
    "piece": "шт",
    "pcs": "шт",
    "шт": "шт",
    "m": "м",
    "m2": "м²",
    "m3": "м³",
    "kg": "кг",
    "ton": "т",
    "liter": "л",
    "l": "л",
    "day": "день",
    "month": "мес",
}


def translate_unit(unit: str) -> str:
    """Перевод единицы измерения с английского на русский."""
    if not unit:
        return "шт"
    unit_lower = str(unit).strip().lower()
    return UNIT_TRANSLATIONS.get(unit_lower, str(unit).strip())


def _to_str(value) -> str:
    """Безопасная конвертация enum/Decimal/str в строку."""
    if value is None:
        return ""
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _to_float(value) -> float:
    """Безопасная конвертация Decimal/str/int в float."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


def _format_money(value) -> str:
    """Форматирование суммы с пробелами (1 234 567.89)."""
    f = _to_float(value)
    return f"{f:,.2f}".replace(",", " ")


def _get_tax_system_label(tax_system: str) -> str:
    """Возвращает русское название системы налогообложения."""
    labels = {
        "osno": "ОСНО",
        "usn_6": 'УСН "Доходы"',
        "usn_15": 'УСН "Доходы-Расходы"',
        "patent": "Патент",
        "npd": "НПД",
    }
    return labels.get(tax_system, tax_system or "ОСНО")


def generate_invoice_pdf(invoice, contractor=None, local_path: str = None) -> bytes:
    """
    Генерирует профессиональный PDF для счёта с полными реквизитами.
    Использует Jinja2 + HTML шаблон для качества.
    """
    try:
        import os

        from jinja2 import Environment, FileSystemLoader

        # Пытаемся использовать WeasyPrint для HTML → PDF
        try:
            from weasyprint import HTML

            use_weasy = True
        except ImportError:
            use_weasy = False

        # Путь к HTML-шаблону
        templates_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "email_templates"
        )

        env = Environment(loader=FileSystemLoader(templates_dir))
        env.filters["translate_unit"] = translate_unit

        template = env.get_template("invoice_pdf.html")

        # Формируем контекст
        context = {
            "invoice": invoice,
            "contractor": contractor,
            "translate_unit": translate_unit,
            "format_money": _format_money,
            "now": datetime.now(),
        }

        html_content = template.render(**context)

        if use_weasy:
            # Профессиональный PDF через WeasyPrint
            pdf_bytes = HTML(string=html_content).write_pdf()
            return pdf_bytes
        else:
            # Fallback: сохраняем как HTML (временное решение)
            return html_content.encode("utf-8")

    except Exception as e:
        print(f"❌ Ошибка генерации PDF через WeasyPrint: {e}")
        # Fallback на старую FPDF-версию
        return _generate_invoice_pdf_fpdf(invoice, contractor)


def generate_act_pdf(
    act, contractor=None, request=None, local_path: str = None
) -> bytes:
    """
    Генерирует профессиональный PDF для акта с полными реквизитами.
    """
    try:
        import os

        from jinja2 import Environment, FileSystemLoader

        try:
            from weasyprint import HTML

            use_weasy = True
        except ImportError:
            use_weasy = False

        templates_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "email_templates"
        )

        env = Environment(loader=FileSystemLoader(templates_dir))
        env.filters["translate_unit"] = translate_unit

        template = env.get_template("act_pdf.html")

        context = {
            "act": act,
            "contractor": contractor,
            "request": request,
            "translate_unit": translate_unit,
            "format_money": _format_money,
            "now": datetime.now(),
        }

        html_content = template.render(**context)

        if use_weasy:
            pdf_bytes = HTML(string=html_content).write_pdf()
            return pdf_bytes
        else:
            return html_content.encode("utf-8")

    except Exception as e:
        print(f"❌ Ошибка генерации PDF через WeasyPrint: {e}")
        return _generate_act_pdf_fpdf(act, contractor)


def _generate_invoice_pdf_fpdf(invoice, contractor=None) -> bytes:
    """Fallback: старый FPDF-генератор с русскими единицами."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.add_font(
        "DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", uni=True
    )
    pdf.add_font(
        "DejaVu", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", uni=True
    )

    # Заголовок
    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, f"СЧЁТ № {invoice.document_number}", 0, 1, "C")
    pdf.set_font("DejaVu", "", 10)
    pdf.cell(0, 6, f"от {invoice.invoice_date}", 0, 1, "C")
    pdf.ln(5)

    # Поставщик
    pdf.set_font("DejaVu", "B", 11)
    pdf.cell(0, 7, "Поставщик:", 0, 1)
    pdf.set_font("DejaVu", "", 9)
    pdf.multi_cell(
        0,
        5,
        'ООО "СпецТехника Про"\n'
        "Юр. адрес: г. Москва, ул. Примерная, д. 1\n"
        "ИНН: 7700000000 / КПП: 770001001\n"
        'р/с: 40702810000000012345 в ПАО "Сбербанк"\n'
        "БИК: 044525225, к/с: 30101810400000000225",
    )
    pdf.ln(3)

    # Покупатель
    pdf.set_font("DejaVu", "B", 11)
    pdf.cell(0, 7, "Покупатель:", 0, 1)
    pdf.set_font("DejaVu", "", 9)
    if contractor:
        info = contractor.name or ""
        if contractor.legal_address:
            info += f"\nЮр. адрес: {contractor.legal_address}"
        if contractor.inn:
            kpp = f" / КПП: {contractor.kpp}" if contractor.kpp else ""
            info += f"\nИНН: {contractor.inn}{kpp}"
        if contractor.bank_details:
            bd = contractor.bank_details
            if bd.get("account"):
                info += f"\nр/с: {bd['account']}"
            if bd.get("bank_name"):
                info += f"\n{bd['bank_name']}"
            if bd.get("bik"):
                info += f"\nБИК: {bd['bik']}"
        if contractor.tax_system:
            info += f"\nСистема налогообложения: {_get_tax_system_label(contractor.tax_system)}"
        pdf.multi_cell(0, 5, info)
    else:
        pdf.cell(0, 5, "Не указан", 0, 1)
    pdf.ln(5)

    # Таблица позиций
    pdf.set_font("DejaVu", "B", 10)
    pdf.cell(10, 7, "№", 1, 0, "C")
    pdf.cell(100, 7, "Наименование", 1, 0, "C")
    pdf.cell(20, 7, "Ед.", 1, 0, "C")
    pdf.cell(15, 7, "Кол-во", 1, 0, "C")
    pdf.cell(25, 7, "Цена", 1, 0, "C")
    pdf.cell(20, 7, "Сумма", 1, 1, "C")

    pdf.set_font("DejaVu", "", 9)
    for idx, item in enumerate(invoice.items, 1):
        unit = translate_unit(getattr(item, "unit", "шт") or "шт")
        pdf.cell(10, 6, str(idx), 1, 0, "C")
        pdf.cell(100, 6, str(item.description or "")[:60], 1, 0, "L")
        pdf.cell(20, 6, unit, 1, 0, "C")
        pdf.cell(15, 6, str(item.quantity), 1, 0, "C")
        pdf.cell(25, 6, _format_money(item.unit_price), 1, 0, "R")
        pdf.cell(20, 6, _format_money(item.amount), 1, 1, "R")

    pdf.ln(5)

    # Итоги
    subtotal = _to_float(invoice.subtotal)
    total = _to_float(invoice.total)
    vat_amount = _to_float(invoice.vat_amount)
    tax_system = getattr(invoice, "tax_system", "osno")

    pdf.set_font("DejaVu", "", 10)
    pdf.cell(150, 7, "Итого:", 0, 0, "R")
    pdf.cell(40, 7, f"{_format_money(subtotal)} ₽", 0, 1, "R")

    if tax_system == "osno" and vat_amount > 0:
        vat_rate = _to_float(invoice.vat_rate)
        pdf.cell(150, 7, f"НДС ({vat_rate}%):", 0, 0, "R")
        pdf.cell(40, 7, f"{_format_money(vat_amount)} ₽", 0, 1, "R")
    else:
        label = _get_tax_system_label(tax_system)
        pdf.cell(150, 7, f"НДС: Без НДС ({label})", 0, 0, "R")
        pdf.cell(40, 7, "", 0, 1, "R")

    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(150, 8, "Всего к оплате:", 0, 0, "R")
    pdf.cell(40, 8, f"{_format_money(total)} ₽", 0, 1, "R")

    # Футер
    pdf.ln(10)
    pdf.set_font("DejaVu", "I", 8)
    pdf.cell(
        0,
        5,
        f'Документ сгенерирован: {datetime.now().strftime("%d.%m.%Y %H:%M")}',
        0,
        1,
        "C",
    )
    pdf.cell(0, 5, 'Система "СпецТехника Про"', 0, 1, "C")

    return bytes(pdf.output())


def _generate_act_pdf_fpdf(act, contractor=None) -> bytes:
    """Fallback: старый FPDF-генератор с русскими единицами."""
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.add_font(
        "DejaVu", "", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", uni=True
    )
    pdf.add_font(
        "DejaVu", "B", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", uni=True
    )

    # Заголовок
    pdf.set_font("DejaVu", "B", 16)
    pdf.cell(0, 10, f"АКТ № {act.document_number}", 0, 1, "C")
    pdf.set_font("DejaVu", "", 10)
    pdf.cell(0, 6, f"от {act.act_date}", 0, 1, "C")
    pdf.ln(5)

    # Исполнитель
    pdf.set_font("DejaVu", "B", 11)
    pdf.cell(0, 7, "Исполнитель:", 0, 1)
    pdf.set_font("DejaVu", "", 9)
    pdf.multi_cell(
        0,
        5,
        'ООО "СпецТехника Про"\n'
        "Юр. адрес: г. Москва, ул. Примерная, д. 1\n"
        "ИНН: 7700000000 / КПП: 770001001\n"
        'р/с: 40702810000000012345 в ПАО "Сбербанк"\n'
        "БИК: 044525225, к/с: 30101810400000000225",
    )
    pdf.ln(3)

    # Заказчик
    pdf.set_font("DejaVu", "B", 11)
    pdf.cell(0, 7, "Заказчик:", 0, 1)
    pdf.set_font("DejaVu", "", 9)
    if contractor:
        info = contractor.name or ""
        if contractor.legal_address:
            info += f"\nЮр. адрес: {contractor.legal_address}"
        if contractor.inn:
            kpp = f" / КПП: {contractor.kpp}" if contractor.kpp else ""
            info += f"\nИНН: {contractor.inn}{kpp}"
        if contractor.bank_details:
            bd = contractor.bank_details
            if bd.get("account"):
                info += f"\nр/с: {bd['account']}"
            if bd.get("bank_name"):
                info += f"\n{bd['bank_name']}"
            if bd.get("bik"):
                info += f"\nБИК: {bd['bik']}"
        if contractor.tax_system:
            info += f"\nСистема налогообложения: {_get_tax_system_label(contractor.tax_system)}"
        pdf.multi_cell(0, 5, info)
    else:
        pdf.cell(0, 5, "Не указан", 0, 1)
    pdf.ln(5)

    # Сумма
    total = _to_float(act.total_amount)
    tax_system = getattr(act, "tax_system", "osno")

    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(150, 8, "Итого:", 0, 0, "R")
    pdf.cell(40, 8, f"{_format_money(total)} ₽", 0, 1, "R")

    if tax_system == "osno":
        vat_rate = _to_float(getattr(act, "vat_rate", 20))
        vat_included = getattr(act, "is_vat_included", True)
        if vat_included:
            vat = total * vat_rate / (100 + vat_rate)
            pdf.cell(150, 7, f"НДС ({vat_rate}%, включён):", 0, 0, "R")
        else:
            vat = total * vat_rate / 100
            pdf.cell(150, 7, f"НДС ({vat_rate}%, сверху):", 0, 0, "R")
        pdf.cell(40, 7, f"{_format_money(vat)} ₽", 0, 1, "R")
    else:
        label = _get_tax_system_label(tax_system)
        pdf.cell(150, 7, f"НДС: Без НДС ({label})", 0, 0, "R")
        pdf.cell(40, 7, "", 0, 1, "R")

    pdf.set_font("DejaVu", "B", 12)
    pdf.cell(150, 8, "Всего к оплате:", 0, 0, "R")
    pdf.cell(40, 8, f"{_format_money(total)} ₽", 0, 1, "R")

    # Подписи
    pdf.ln(20)
    pdf.set_font("DejaVu", "B", 11)
    pdf.cell(95, 7, "Исполнитель", 0, 0, "C")
    pdf.cell(95, 7, "Заказчик", 0, 1, "C")
    pdf.ln(15)
    pdf.set_font("DejaVu", "", 9)
    pdf.cell(95, 5, "М.П. / ________________", 0, 0, "C")
    pdf.cell(95, 5, "М.П. / ________________", 0, 1, "C")

    # Футер
    pdf.ln(10)
    pdf.set_font("DejaVu", "I", 8)
    pdf.cell(
        0,
        5,
        f'Документ сгенерирован: {datetime.now().strftime("%d.%m.%Y %H:%M")}',
        0,
        1,
        "C",
    )
    pdf.cell(0, 5, 'Система "СпецТехника Про"', 0, 1, "C")

    return bytes(pdf.output())


def generate_payout_pdf(payout, owner_name: str = "", vehicle_name: str = "", local_path: str = None) -> bytes:
    """Генерирует PDF ведомости выплаты собственнику."""
    try:
        from fpdf import FPDF

        pdf = FPDF()
        pdf.add_page()

        # Пытаемся добавить шрифт с поддержкой кириллицы
        font_added = False
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/Arial.ttf",
        ]

        for fp in font_paths:
            try:
                from pathlib import Path
                if Path(fp).exists():
                    pdf.add_font("UniFont", "", fp, uni=True)
                    pdf.add_font("UniFont", "B", fp, uni=True)
                    font_added = True
                    break
            except Exception:
                continue

        if not font_added:
            # Fallback на стандартный шрифт (без кириллицы)
            pass

        def _font(style="", size=10):
            if font_added:
                pdf.set_font("UniFont", style, size)
            else:
                pdf.set_font("Helvetica", style, size)

        # Заголовок
        _font("B", 18)
        pdf.cell(0, 12, f"VEDOMOST VYPLATY", 0, 1, "C")
        _font("", 10)
        pdf.cell(0, 6, f"{payout.document_number or ''}", 0, 1, "C")
        pdf.ln(5)

        # Информация о выплате
        _font("B", 12)
        pdf.cell(0, 8, "DETALI VYPLATY", 0, 1)
        pdf.ln(2)

        details = [
            ("Nomera dokumenta", payout.document_number or "N/A"),
            ("Data vyplaty", str(payout.payout_date or "N/A")),
            ("Status", str(getattr(payout.status, 'value', payout.status) if payout.status else "N/A")),
            ("Sobstvennik", owner_name or "N/A"),
            ("Tekhnika", vehicle_name or "N/A"),
        ]

        _font("", 10)
        for label, value in details:
            pdf.cell(70, 7, f"{label}:", 0, 0)
            pdf.cell(0, 7, str(value), 0, 1)

        pdf.ln(5)

        # Финансовые детали
        _font("B", 12)
        pdf.cell(0, 8, "FINANSOVYE DETALI", 0, 1)
        pdf.ln(2)

        gross = float(payout.gross_amount or 0)
        commission = float(payout.platform_commission or 0)
        net = float(payout.net_amount or 0)
        rate = float(payout.commission_rate or 0)

        finance_rows = [
            ("Gross suma", f"{gross:,.2f} RUB".replace(",", " ")),
            (f"Komissiya platformy ({rate}%)", f"- {commission:,.2f} RUB".replace(",", " ")),
            ("K vyplate (Net)", f"{net:,.2f} RUB".replace(",", " ")),
        ]

        for label, value in finance_rows:
            _font("", 10)
            pdf.cell(100, 7, f"{label}:", 0, 0)
            _font("B", 10)
            pdf.cell(0, 7, value, 0, 1)

        pdf.ln(3)

        # Выделяем итоговую сумму
        _font("B", 14)
        pdf.cell(100, 10, "ITOGO K VYPLATE:", 0, 0)
        pdf.cell(0, 10, f"{net:,.2f} RUB".replace(",", " "), 0, 1)

        # Подписи
        pdf.ln(20)
        _font("", 9)
        pdf.cell(95, 7, "Podpis' menedzhera", 0, 0, "C")
        pdf.cell(95, 7, "Podpis' sobstvennika", 0, 1, "C")
        pdf.ln(15)
        pdf.cell(95, 5, "M.P. / ________________", 0, 0, "C")
        pdf.cell(95, 5, "M.P. / ________________", 0, 1, "C")

        # Футер
        pdf.ln(10)
        _font("I", 8)
        pdf.cell(0, 5, f'Dokument sgenerirovan: {datetime.now().strftime("%d.%m.%Y %H:%M")}', 0, 1, "C")
        pdf.cell(0, 5, 'Sistema "SpecTekhnika Pro"', 0, 1, "C")

        result = bytes(pdf.output())
        if len(result) < 100:
            logger.warning(f"⚠️ Generated payout PDF too small: {len(result)} bytes")
        return result

    except Exception as e:
        logger.error(f"❌ Failed to generate payout PDF: {e}", exc_info=True)
        return b""


def generate_maintenance_order_pdf(order_data: dict, local_path: str = None) -> bytes:
    """
    Генерирует PDF наряд-заказа на техническое обслуживание.
    """
    try:
        import os

        from jinja2 import Environment, FileSystemLoader
        from weasyprint import HTML

        templates_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "email_templates"
        )

        env = Environment(loader=FileSystemLoader(templates_dir))
        template = env.get_template("maintenance_order.html")

        context = {
            "order": order_data,
            "format_money": _format_money,
            "now": datetime.now(),
        }

        html_content = template.render(**context)
        pdf_bytes = HTML(string=html_content).write_pdf()
        return pdf_bytes

    except Exception as e:
        print(f"❌ Ошибка генерации PDF наряд-заказа: {e}")
        # Fallback: возвращаем простой HTML
        fallback_html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"><title>Наряд-заказ {order_data.get('order_number', '')}</title></head>
        <body>
            <h1>НАРЯД-ЗАКАЗ № {order_data.get('order_number', '')}</h1>
            <p><strong>Техника:</strong> {order_data.get('vehicle_name', 'N/A')}</p>
            <p><strong>Статус:</strong> {order_data.get('status', 'N/A')}</p>
            <p><strong>Название:</strong> {order_data.get('title', 'N/A')}</p>
            <p><strong>Итого:</strong> {order_data.get('total_cost', 0)} ₽</p>
            <p style="color: red;">⚠️ PDF-генерация недоступна (WeasyPrint не установлен или шаблон не найден)</p>
        </body>
        </html>
        """
        return fallback_html.encode("utf-8")


def generate_act_maintenance_pdf(order_data: dict, local_path: str = None) -> bytes:
    """
    Генерирует PDF акта выполненных работ для наряд-заказа.
    """
    try:
        import os

        from jinja2 import Environment, FileSystemLoader
        from weasyprint import HTML

        templates_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "email_templates"
        )

        env = Environment(loader=FileSystemLoader(templates_dir))
        template = env.get_template("act_maintenance.html")

        context = {
            "order": order_data,
            "format_money": _format_money,
            "now": datetime.now(),
        }

        html_content = template.render(**context)
        pdf_bytes = HTML(string=html_content).write_pdf()
        return pdf_bytes

    except Exception as e:
        print(f"❌ Ошибка генерации PDF акта: {e}")
        fallback_html = f"""
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"><title>Акт {order_data.get('order_number', '')}</title></head>
        <body>
            <h1>АКТ ВЫПОЛНЕННЫХ РАБОТ № {order_data.get('order_number', '')}</h1>
            <p><strong>Техника:</strong> {order_data.get('vehicle_name', 'N/A')}</p>
            <p><strong>Итого:</strong> {order_data.get('total_cost', 0)} ₽</p>
            <p style="color: red;">⚠️ PDF-генерация недоступна: {e}</p>
        </body>
        </html>
        """
        return fallback_html.encode("utf-8")
