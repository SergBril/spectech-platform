"""Генерация УПД и ТОРГ-12 через ReportLab (официальные формы, ред. 2026)."""

import logging
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger("spectech.reportlab_pdf")

# === Регистрация кириллических шрифтов ===
_FONTS_DIR = Path(__file__).parent / "fonts"
_REGULAR_FONT = _FONTS_DIR / "DejaVuSans.ttf"
_BOLD_FONT = _FONTS_DIR / "DejaVuSans-Bold.ttf"

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

# Приоритет 1: локальные шрифты (Windows/macOS/Docker with volume)
if _REGULAR_FONT.exists() and _BOLD_FONT.exists():
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", str(_REGULAR_FONT)))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(_BOLD_FONT)))
        FONT_REGULAR = "DejaVu"
        FONT_BOLD = "DejaVu-Bold"
        logger.info("✅ DejaVu fonts loaded from %s", _FONTS_DIR)
    except Exception as e:
        logger.warning("⚠️ DejaVu font registration failed: %s", e)

# Приоритет 2: системные пути (Linux/Docker)
if FONT_REGULAR == "Helvetica":
    _SYSTEM_PATHS = [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
        Path("/app/fonts/DejaVuSans.ttf"),
    ]
    for _p in _SYSTEM_PATHS:
        if _p.exists():
            try:
                pdfmetrics.registerFont(TTFont("DejaVu", str(_p)))
                bold_p = _p.parent / "DejaVuSans-Bold.ttf"
                if bold_p.exists():
                    pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(bold_p)))
                FONT_REGULAR = "DejaVu"
                FONT_BOLD = "DejaVu-Bold"
                logger.info("✅ DejaVu fonts loaded from %s", _p)
                break
            except Exception:
                continue
    else:
        logger.warning("No valid Cyrillic font found - PDF will show squares")


def _money_to_words_ru(amount: float) -> str:
    """Сумма прописью на русском."""
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

    def three(n: int, feminine: bool = False) -> str:
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


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(name="RuBody", fontName=FONT_REGULAR, fontSize=7.5, leading=9.5)
    )
    styles.add(
        ParagraphStyle(
            name="RuSmall",
            fontName=FONT_REGULAR,
            fontSize=6,
            leading=7.5,
            textColor=colors.HexColor("#444444"),
        )
    )
    styles.add(
        ParagraphStyle(name="RuBold", fontName=FONT_BOLD, fontSize=10, leading=12)
    )
    return styles


def _calc(act):
    """Единый расчёт сумм: ОСНО без ставки -> НДС 22% (ред. 01.01.2026)."""
    vat_rate = float(act.vat_rate or 0)
    if act.tax_system == "osno" and vat_rate <= 0:
        vat_rate = 22.0
    show_vat = act.tax_system == "osno"
    total = float(act.total_amount or 0)
    if show_vat:
        subtotal = total / (1 + vat_rate / 100)
        vat = total - subtotal
        status = "1"
    else:
        subtotal, vat, status = total, 0.0, "2"
    return vat_rate, show_vat, subtotal, vat, total, status


def _num(value: float) -> str:
    """Формат чисел в стиле 1С: 62 900.01 (пробел для тысяч)."""
    return f"{value:,.2f}".replace(",", " ")


def _qty(value: float) -> str:
    """Формат количества в стиле 1С: 1,000."""
    return f"{value:,.3f}".replace(",", " ").replace(".", ",")


def _grid(style_extra=None):
    base = [
        ("FONTNAME", (0, 0), (-1, -1), FONT_REGULAR),
        ("FONTSIZE", (0, 0), (-1, -1), 6.5),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    return TableStyle(base + (style_extra or []))


class _NumberedCanvas(canvas.Canvas):
    """Canvas с футером 'Страница X из Y' и колонтитулом 'продолжение' со 2-й стр."""

    def __init__(self, *args, doc_title: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_pages = []
        self._doc_title = doc_title

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_pages)
        for state in self._saved_pages:
            self.__dict__.update(state)
            self._draw_decorations(total)
            super().showPage()
        super().save()

    def _draw_decorations(self, total: int):
        width, height = landscape(A4)
        self.saveState()
        self.setFont(FONT_REGULAR, 7)
        self.setFillColor(colors.HexColor("#444444"))
        self.setStrokeColor(colors.HexColor("#999999"))
        self.setLineWidth(0.3)
        # Футер: слева документ, справа номер страницы
        self.line(8 * mm, 6 * mm, width - 8 * mm, 6 * mm)
        self.drawString(8 * mm, 4.2 * mm, self._doc_title)
        self.drawRightString(
            width - 8 * mm, 4.2 * mm, f"Страница {self._pageNumber} из {total}"
        )
        # Со 2-й страницы: колонтитул "продолжение"
        if self._pageNumber > 1:
            self.line(8 * mm, height - 6 * mm, width - 8 * mm, height - 6 * mm)
            self.drawString(
                8 * mm, height - 4.5 * mm, f"{self._doc_title} - продолжение"
            )
        self.restoreState()


def _canvas_factory(doc_title: str):
    """Фабрика canvas для doc.build(canvasmaker=...)."""

    def factory(*args, **kwargs):
        return _NumberedCanvas(*args, doc_title=doc_title, **kwargs)

    return factory


def _build_items(items, work, subtotal, vat, total):
    """Список позиций: из items либо одна (весь акт одной услугой)."""
    if items:
        return items
    return [
        {
            "description": work,
            "unit": "шт",
            "quantity": 1.0,
            "unit_price": subtotal,
            "subtotal": subtotal,
            "vat_amount": vat,
            "total": total,
        }
    ]


def generate_upd_reportlab(act, company, client, request=None, items=None) -> bytes:
    """УПД по образцу 1С/Диадок: постановление ПФ РФ №1137 в ред. постановления №26."""
    styles = _styles()
    vat_rate, show_vat, subtotal, vat, total, status = _calc(act)
    basis = f"Заявка №{act.request_id}" if act.request_id else "-"
    work = getattr(request, "work_type", None) or "Работы по акту"
    comp_inn_kpp = f"{company.inn or '-'}/{getattr(company, 'kpp', '') or '-'}"
    clnt_inn_kpp = f"{client.inn or '-'}/{getattr(client, 'kpp', '') or '-'}"
    doc_date = act.act_date.strftime("%d.%m.%Y")
    months = [
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    ]
    doc_date_word = (
        f"{act.act_date.day} {months[act.act_date.month - 1]} {act.act_date.year}"
    )

    rows = _build_items(items, work, subtotal, vat, total)
    if items:
        subtotal = sum(r["subtotal"] for r in rows)
        vat = sum(r["vat_amount"] for r in rows)
        total = sum(r["total"] for r in rows)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=8 * mm,
        rightMargin=8 * mm,
        topMargin=8 * mm,
        bottomMargin=10 * mm,
    )
    story = []

    # ── ШАПКА: статус слева + продавец/покупатель на одном уровне ──
    left = Paragraph(
        "<b>Универсальный<br/>передаточный<br/>документ</b><br/><br/>"
        f"Статус: <b>{status}</b><br/><br/>"
        "<font size=6>1 - счет-фактура и<br/>передаточный документ (акт)<br/>"
        "2 - передаточный документ<br/>(акт)</font>",
        styles["RuBody"],
    )
    hdr = [
        [
            left,
            Paragraph(
                f"Счет-фактура № <b>{act.document_number}</b> от <b>{doc_date_word}</b> (1)<br/>"
                f"Исправление № - от - (1а)<br/>"
                f"<b>Продавец:</b> {company.name} (2)<br/>"
                f"Адрес: {company.legal_address or '-'} (2а)<br/>"
                f"ИНН/КПП продавца: {comp_inn_kpp} (2б)<br/>"
                f"Грузоотправитель и его адрес: {company.name} (3)<br/>"
                f"К платежно-расчетному документу № - от - (5)<br/>"
                f"Документ об отгрузке: № - от - (5а)",
                styles["RuBody"],
            ),
            Paragraph(
                f"<b>Покупатель:</b> {client.name} (6)<br/>"
                f"Адрес: {client.legal_address or '-'} (6а)<br/>"
                f"ИНН/КПП покупателя: {clnt_inn_kpp} (6б)<br/>"
                f"Грузополучатель и его адрес: {client.name} (4)<br/>"
                f"Валюта: наименование, код: Российский рубль, 643 (7)<br/>"
                f"Идентификатор государственного контракта,<br/>договора (соглашения) (при наличии): {basis} (8)",
                styles["RuBody"],
            ),
        ],
    ]
    t = Table(hdr, colWidths=[40 * mm, 118 * mm, 119 * mm])
    t.setStyle(
        _grid(
            [
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#fafafa")),
                ("VALIGN", (0, 0), (0, 0), "MIDDLE"),
            ]
        )
    )
    story.append(t)
    story.append(
        Paragraph(
            "<font size=6>Приложение № 1 к постановлению Правительства Российской Федерации "
            "от 26 декабря 2011 г. № 1137 (в редакции постановления Правительства Российской "
            "Федерации от 23 января 2026 г. № 26)</font>",
            styles["RuSmall"],
        )
    )
    story.append(Spacer(1, 1.5 * mm))

    # ── ТАБЛИЦА ТОВАРОВ: 3 строки заголовка, повтор на каждой странице ──
    W = [w * mm for w in [6, 9, 96, 8, 7, 9, 11, 14, 16, 10, 8, 14, 16, 7, 9, 12]]
    h0 = [
        "№ п/п",
        "Код товара/ работ, услуг",
        "Наименование товара (описание выполненных работ, оказанных услуг), имущественного права",
        "Код вида товара",
        "Единица измерения",
        "",
        "Коли-чество (объем)",
        "Цена (тариф) за единицу измерения",
        "Стоимость товаров (работ, услуг), имущественных прав без налога - всего",
        "В том числе сумма акциза",
        "Налоговая ставка",
        "Сумма налога, предъявляемая покупателю",
        "Стоимость товаров (работ, услуг), имущественных прав с налогом - всего",
        "Страна происхождения товара",
        "",
        "Регистрационный номер декларации",
    ]
    h1 = [
        "",
        "",
        "",
        "",
        "код",
        "условное обозначение (национальное)",
        "",
        "",
        "",
        "",
        "",
        "",
        "",
        "цифровой код",
        "краткое наименование",
        "",
    ]
    h2 = [
        "1",
        "А",
        "1а",
        "1б",
        "2",
        "2а",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "10а",
        "11",
    ]
    data = [h0, h1, h2]
    spans = [("SPAN", (4, 0), (5, 0)), ("SPAN", (13, 0), (14, 0))]
    for c in [0, 1, 2, 3, 6, 7, 8, 9, 10, 11, 12, 15]:
        spans.append(("SPAN", (c, 0), (c, 1)))

    for idx, it in enumerate(rows, start=1):
        data.append(
            [
                str(idx),
                "-",
                it["description"],
                "-",
                "-",
                it["unit"],
                _qty(it["quantity"]),
                _num(it["unit_price"]),
                _num(it["subtotal"]),
                "без акциза",
                f"{vat_rate:.0f}%" if show_vat else "Без НДС",
                _num(it["vat_amount"]) if show_vat else "-",
                _num(it["total"]),
                "-",
                "-",
                "-",
            ]
        )

    last = len(data)
    data.append(
        [
            "Всего к оплате (9)",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            _num(subtotal),
            "Х",
            f"{vat_rate:.0f}%" if show_vat else "Х",
            _num(vat) if show_vat else "Х",
            _num(total),
            "",
            "",
            "",
        ]
    )
    spans.append(("SPAN", (0, last), (7, last)))
    t = Table(data, colWidths=W, repeatRows=3)
    t.setStyle(
        _grid(
            spans
            + [
                ("BACKGROUND", (0, 0), (-1, 2), colors.HexColor("#eeeeee")),
                ("BACKGROUND", (0, last), (-1, last), colors.HexColor("#f5f5f5")),
                ("FONTNAME", (0, last), (-1, last), FONT_BOLD),
                ("ALIGN", (0, 2), (-1, 2), "CENTER"),
                ("FONTSIZE", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 2 * mm))

    story.append(
        Paragraph(
            f"Всего наименований: {len(rows)}. Сумма без НДС: {_num(subtotal)} руб. "
            + (
                f"НДС {vat_rate:.0f}%: {_num(vat)} руб. "
                if show_vat
                else "НДС: без НДС. "
            )
            + f"<b>ВСЕГО К ОПЛАТЕ: {_num(total)} руб.</b> ({_money_to_words_ru(total)})",
            styles["RuBody"],
        )
    )
    story.append(Spacer(1, 3 * mm))

    # ── Подписи составителя ──
    story.append(Paragraph("Документ составлен на листах: ____", styles["RuBody"]))
    sig = [
        [
            Paragraph(
                "Руководитель организации или иное уполномоченное лицо<br/>"
                "Генеральный директор ______________ (подпись) ______________ (ф.и.о.)",
                styles["RuBody"],
            ),
            Paragraph(
                "Главный бухгалтер или иное уполномоченное лицо<br/>"
                "______________ (подпись) ______________ (ф.и.о.)",
                styles["RuBody"],
            ),
        ],
        [
            Paragraph(
                "Индивидуальный предприниматель или иное уполномоченное лицо<br/>"
                "______________ (подпись) ______________ (ф.и.о.)",
                styles["RuBody"],
            ),
            Paragraph(
                "<font size=6>(реквизиты свидетельства о государственной регистрации "
                "индивидуального предпринимателя)</font>",
                styles["RuSmall"],
            ),
        ],
    ]
    sig_t = Table(sig, colWidths=[138 * mm, 139 * mm])
    sig_t.setStyle(
        _grid(
            [
                ("BOX", (0, 0), (-1, -1), 0, colors.white),
                ("INNERGRID", (0, 0), (-1, -1), 0, colors.white),
            ]
        )
    )

    # ── Блок передачи/получения [8]-[19] ──
    tr = [
        [
            Paragraph(
                f"Основание передачи (сдачи)/ получения (приемки) <b>{basis}</b> [8]<br/>"
                f"<font size=6>(договор; доверенность и др.)</font><br/>"
                f"Данные о транспортировке и грузе: - [9]<br/>"
                f"Товар (груз) передал/ услуги, результаты работ, права сдал [10]:<br/>"
                f"Генеральный директор ______________ (подпись) ______________ (ф.и.о.)<br/>"
                f"Дата отгрузки, передачи (сдачи) «{act.act_date.day}» "
                f"{months[act.act_date.month - 1]} {act.act_date.year} [11]<br/>"
                f"Иные сведения об отгрузке, передаче [12]: -<br/>"
                f"Ответственный за правильность оформления факта хозяйственной жизни [13]:<br/>"
                f"Генеральный директор ______________ (подпись) ______________ (ф.и.о.)<br/>"
                f"Наименование экономического субъекта - составителя документа [14]:<br/>"
                f"{company.name}, ИНН/КПП {comp_inn_kpp}<br/>М.П.",
                styles["RuBody"],
            ),
            Paragraph(
                f"Товар (груз) получил/ услуги, результаты работ, права принял [15]:<br/>"
                f"Генеральный директор ______________ (подпись) ______________ (ф.и.о.)<br/>"
                f"Дата получения (приемки) «__» ____________ 20__ года [16]<br/>"
                f"Иные сведения о получении, приемке [17]: -<br/>"
                f"Ответственный за правильность оформления факта хозяйственной жизни [18]:<br/>"
                f"______________ (подпись) ______________ (ф.и.о.)<br/>"
                f"Наименование экономического субъекта - составителя документа [19]:<br/>"
                f"{client.name}, ИНН/КПП {clnt_inn_kpp}<br/>М.П.",
                styles["RuBody"],
            ),
        ]
    ]
    tr_t = Table(tr, colWidths=[138 * mm, 139 * mm])
    tr_t.setStyle(_grid())

    # Подписи и блок передачи НЕ рвутся между страницами
    story.append(KeepTogether([sig_t, Spacer(1, 2 * mm), tr_t]))
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            "УПД сгенерирован в системе «СпецТехника Про» • Форма по письму ФНС России от 21.10.2013 "
            "№ ММВ-20-3/96@ в редакции постановления Правительства РФ от 23.01.2026 № 26 "
            "(действует с 01.04.2026)",
            styles["RuSmall"],
        )
    )

    title = f"УПД № {act.document_number} от {doc_date}"
    doc.build(story, canvasmaker=_canvas_factory(title))
    pdf = buf.getvalue()
    logger.info("UPD PDF generated via ReportLab: %s bytes", len(pdf))
    return pdf


def generate_torg12_reportlab(
    act, company, client, request=None, driver_name=None, vehicle_plate=None, items=None
) -> bytes:
    """ТОРГ-12 по ОКУД 0330212 (Постановление Госкомстата РФ от 25.12.1998 № 132)."""
    styles = _styles()
    vat_rate, show_vat, subtotal, vat, total, _ = _calc(act)
    bd_c = getattr(company, "bank_details", None) or {}
    bd_k = getattr(client, "bank_details", None) or {}
    basis = f"Заявка №{act.request_id}" if act.request_id else "-"
    work = getattr(request, "work_type", None) or "Товар по накладной"
    comp_inn_kpp = f"{company.inn or '-'}/{getattr(company, 'kpp', '') or '-'}"
    clnt_inn_kpp = f"{client.inn or '-'}/{getattr(client, 'kpp', '') or '-'}"
    doc_date = act.act_date.strftime("%d.%m.%Y")

    rows = _build_items(items, work, subtotal, vat, total)
    if items:
        subtotal = sum(r["subtotal"] for r in rows)
        vat = sum(r["vat_amount"] for r in rows)
        total = sum(r["total"] for r in rows)
    total_qty = sum(r["quantity"] for r in rows)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=8 * mm,
        rightMargin=8 * mm,
        topMargin=8 * mm,
        bottomMargin=10 * mm,
    )
    story = []

    # ── ШАПКА с грифом и кодом ОКУД ──
    stamp = Paragraph(
        "Унифицированная форма № ТОРГ-12<br/>"
        "Утверждена постановлением Госкомстата России<br/>"
        "от 25.12.1998 № 132",
        styles["RuSmall"],
    )
    codes = [
        ["", "", "Коды"],
        ["Форма по ОКУД", "0330212", ""],
        ["", "", "по ОКПО"],
        [company.name, "", "-"],
        ["", "Вид деятельности по ОКДП", ""],
        ["структурное подразделение", "", "по ОКПО"],
    ]
    ct = Table(codes, colWidths=[80 * mm, 50 * mm, 30 * mm])
    ct.setStyle(
        _grid(
            [
                ("SPAN", (1, 2), (2, 2)),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
            ]
        )
    )
    ht = Table([[stamp, ct]], colWidths=[70 * mm, 207 * mm])
    ht.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 0, colors.white),
            ]
        )
    )
    story.append(ht)
    story.append(Spacer(1, 2 * mm))

    # ── Реквизиты сторон ──
    def party(label, name, address, inn_kpp, bd):
        return Paragraph(
            f"<b>{label}</b>, адрес, банковские реквизиты<br/>"
            f"{name}, {address}<br/>"
            f"<font size=5>ИНН/КПП: {inn_kpp}; Банк: {bd.get('bank_name', '-')}<br/>"
            f"р/с: {bd.get('account', '-')}, к/с: {bd.get('correspondent_account', '-')}</font>",
            styles["RuBody"],
        )

    parties = [
        [
            party(
                "Грузоотправитель",
                company.name,
                company.legal_address or "-",
                comp_inn_kpp,
                bd_c,
            ),
            Paragraph("<b>по ОКПО</b><br/>-", styles["RuBody"]),
            party(
                "Грузополучатель",
                client.name,
                client.legal_address or "-",
                clnt_inn_kpp,
                bd_k,
            ),
            Paragraph("<b>по ОКПО</b><br/>-", styles["RuBody"]),
        ],
        [
            party(
                "Поставщик",
                company.name,
                company.legal_address or "-",
                comp_inn_kpp,
                bd_c,
            ),
            Paragraph("<b>по ОКПО</b><br/>-", styles["RuBody"]),
            party(
                "Плательщик",
                client.name,
                client.legal_address or "-",
                clnt_inn_kpp,
                bd_k,
            ),
            Paragraph("<b>по ОКПО</b><br/>-", styles["RuBody"]),
        ],
    ]
    t = Table(parties, colWidths=[100 * mm, 20 * mm, 100 * mm, 20 * mm])
    t.setStyle(
        _grid(
            [
                ("BOX", (0, 0), (-1, -1), 0, colors.white),
                ("INNERGRID", (0, 0), (-1, -1), 0, colors.white),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 2 * mm))

    story.append(
        Paragraph(
            f"<font size=13><b>РАСХОДНАЯ НАКЛАДНАЯ № {act.document_number}</b></font> "
            f"от <b>{doc_date}</b>. Основание: {basis}",
            styles["RuBody"],
        )
    )
    story.append(Spacer(1, 2 * mm))

    # ── ТАБЛИЦА ТОВАРОВ: 15 граф, повтор шапки на каждой странице ──
    W = [w * mm for w in [8, 10, 60, 10, 8, 10, 10, 10, 10, 10, 10, 12, 14, 14, 16]]
    h0 = [
        "№ п/п",
        "Товар",
        "",
        "Единица измерения",
        "",
        "Вид упаковки",
        "Количество",
        "",
        "Масса брутто",
        "Количество (масса нетто)",
        "Цена, руб. коп.",
        "Сумма без учёта НДС, руб. коп.",
        "НДС",
        "",
        "Сумма с учётом НДС, руб. коп.",
    ]
    h1 = [
        "",
        "наименование, характеристика, сорт, артикул товара",
        "код",
        "наименование",
        "код по ОКЕИ",
        "",
        "в одном месте",
        "мест, штук",
        "",
        "",
        "",
        "",
        "ставка, %",
        "сумма, руб. коп.",
        "",
    ]
    h2 = [
        "1",
        "2",
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "11",
        "12",
        "13",
        "14",
        "15",
    ]
    data = [h0, h1, h2]
    spans = [
        ("SPAN", (0, 0), (0, 2)),
        ("SPAN", (1, 0), (2, 0)),
        ("SPAN", (3, 0), (4, 0)),
        ("SPAN", (5, 0), (5, 2)),
        ("SPAN", (6, 0), (7, 0)),
        ("SPAN", (8, 0), (8, 2)),
        ("SPAN", (9, 0), (9, 2)),
        ("SPAN", (10, 0), (10, 2)),
        ("SPAN", (11, 0), (11, 2)),
        ("SPAN", (12, 0), (13, 0)),
        ("SPAN", (14, 0), (14, 2)),
    ]

    for idx, it in enumerate(rows, start=1):
        data.append(
            [
                str(idx),
                it["description"],
                "-",
                it["unit"],
                "796",
                "-",
                "1",
                _qty(it["quantity"]),
                "-",
                _qty(it["quantity"]),
                _num(it["unit_price"]),
                _num(it["subtotal"]),
                f"{vat_rate:.0f}" if show_vat else "без НДС",
                _num(it["vat_amount"]) if show_vat else "без НДС",
                _num(it["total"]),
            ]
        )

    last = len(data)
    data.append(
        [
            "Итого",
            "",
            "",
            "",
            "",
            "",
            "",
            _qty(total_qty),
            "-",
            _qty(total_qty),
            "Х",
            _num(subtotal),
            "Х",
            _num(vat) if show_vat else "Х",
            _num(total),
        ]
    )
    spans.append(("SPAN", (0, last), (6, last)))
    t = Table(data, colWidths=W, repeatRows=3)
    t.setStyle(
        _grid(
            spans
            + [
                ("BACKGROUND", (0, 0), (-1, 2), colors.HexColor("#eeeeee")),
                ("BACKGROUND", (0, last), (-1, last), colors.HexColor("#f5f5f5")),
                ("FONTNAME", (0, last), (-1, last), FONT_BOLD),
                ("ALIGN", (0, 2), (-1, 2), "CENTER"),
                ("FONTSIZE", (0, 0), (-1, -1), 6.5),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 2 * mm))

    story.append(
        Paragraph(
            f"Товарная накладная имеет приложение на <b>-</b> листах и содержит "
            f"<b>{len(rows)}</b> порядковых номеров записей.<br/>"
            f"Всего отпущено <b>{len(rows)}</b> наименований на сумму "
            f"<b>{_money_to_words_ru(total)}</b>",
            styles["RuBody"],
        )
    )
    story.append(Spacer(1, 3 * mm))

    # ── Подписи (не рвутся между страницами) ──
    sig = [
        [
            Paragraph(
                "Отпуск груза разрешил:<br/>____________ (должность) "
                "____________ (подпись) ____________ (расшифровка подписи)",
                styles["RuBody"],
            ),
            Paragraph(
                "Главный (старший) бухгалтер:<br/>____________ (подпись) "
                "____________ (расшифровка подписи)",
                styles["RuBody"],
            ),
        ],
        [
            Paragraph(
                "Отпуск груза произвёл:<br/>____________ (должность) "
                "____________ (подпись) ____________ (расшифровка подписи)<br/>"
                f'<font size=5>М.П. "{act.act_date.day}" ____________ 20__ года</font>',
                styles["RuBody"],
            ),
            Paragraph(
                "Груз принял:<br/>____________ (должность) "
                "____________ (подпись) ____________ (расшифровка подписи)",
                styles["RuBody"],
            ),
        ],
        [
            Paragraph(
                'По доверенности № ____ от "__" ____________ 20__ года, выданной '
                "____________________________________ (кем, кому)",
                styles["RuBody"],
            ),
            Paragraph(
                "Груз получил (грузополучатель):<br/>____________ (должность) "
                "____________ (подпись) ____________ (расшифровка подписи)<br/>"
                '<font size=5>М.П. "__" ____________ 20__ года</font>',
                styles["RuBody"],
            ),
        ],
    ]
    if driver_name:
        sig.append(
            [
                Paragraph(
                    f"<b>Водитель:</b> {driver_name}"
                    + (
                        f"<br/><b>Автомобиль:</b> {vehicle_plate}"
                        if vehicle_plate
                        else ""
                    ),
                    styles["RuBody"],
                ),
                Paragraph("", styles["RuBody"]),
            ]
        )
    sig_t = Table(sig, colWidths=[138 * mm, 139 * mm])
    sig_t.setStyle(
        _grid(
            [
                ("BOX", (0, 0), (-1, -1), 0, colors.white),
                ("INNERGRID", (0, 0), (-1, -1), 0, colors.white),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(KeepTogether([sig_t]))
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            "Товарная накладная (ТОРГ-12) сформирована в системе «СпецТехника Про» • "
            "Форма по ОКУД 0330212, утв. Постановлением Госкомстата РФ от 25.12.1998 № 132",
            styles["RuSmall"],
        )
    )

    title = f"Товарная накладная № {act.document_number} от {doc_date}"
    doc.build(story, canvasmaker=_canvas_factory(title))
    pdf = buf.getvalue()
    logger.info("TORG-12 PDF generated via ReportLab: %s bytes", len(pdf))
    return pdf
