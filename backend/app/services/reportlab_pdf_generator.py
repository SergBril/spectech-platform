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
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

logger = logging.getLogger("spectech.reportlab_pdf")

# ─────────────────────────────────────────────────────────────
# Регистрация шрифтов с кириллицей (перебор системных путей)
# ─────────────────────────────────────────────────────────────
FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
    Path("/app/fonts/DejaVuSans.ttf"),
]

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"

for _regular in FONT_CANDIDATES:
    _bold = _regular.parent / (
        _regular.stem.replace("DejaVuSans", "DejaVuSans-Bold") + ".ttf"
    )
    try:
        if (
            _regular.exists()
            and _bold.exists()
            and _regular.stat().st_size > 100_000
            and _regular.read_bytes()[:4] == b"\x00\x01\x00\x00"
        ):
            pdfmetrics.registerFont(TTFont("DejaVu", str(_regular)))
            pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(_bold)))
            FONT_REGULAR = "DejaVu"
            FONT_BOLD = "DejaVu-Bold"
            logger.info(f"✅ DejaVu fonts registered from {_regular}")
            break
        if _regular.exists():
            logger.warning(
                f"⚠️ {_regular} exists but invalid (size={_regular.stat().st_size}, "
                f"header={_regular.read_bytes()[:4]!r})"
            )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"⚠️ Font candidate {_regular} failed: {e}")

if FONT_REGULAR == "Helvetica":
    logger.warning(
        "⚠️ No valid Cyrillic font found — PDF will show ■ instead of Russian text"
    )


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
    styles.add(
        ParagraphStyle(name="RuCell", fontName=FONT_REGULAR, fontSize=6.5, leading=8)
    )
    styles.add(
        ParagraphStyle(
            name="RuCellC", fontName=FONT_REGULAR, fontSize=6.5, leading=8, alignment=1
        )
    )
    styles.add(
        ParagraphStyle(
            name="RuCellR", fontName=FONT_REGULAR, fontSize=6.5, leading=8, alignment=2
        )
    )
    return styles


def _calc(act):
    """Единый расчёт сумм: для ОСНО без ставки — НДС 22% по умолчанию (ред. 01.01.2026)."""
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


def generate_upd_reportlab(act, company, client, request=None) -> bytes:
    """УПД по образцу 1С/Диадок: постановление ПФ РФ №1137 в ред. постановления №26 от 23.01.2026."""
    styles = _styles()
    vat_rate, show_vat, subtotal, vat, total, status = _calc(act)
    basis = f"Заявка №{act.request_id}" if act.request_id else "—"
    work = getattr(request, "work_type", None) or "Работы по акту"
    comp_inn_kpp = f"{company.inn or '—'}/{getattr(company, 'kpp', '') or '—'}"
    clnt_inn_kpp = f"{client.inn or '—'}/{getattr(client, 'kpp', '') or '—'}"
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

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=8 * mm,
        rightMargin=8 * mm,
        topMargin=8 * mm,
        bottomMargin=8 * mm,
    )
    story = []

    # ── ШАПКА: статус слева + продавец/покупатель на одном уровне ──
    left = Paragraph(
        "<b>Универсальный<br/>передаточный<br/>документ</b><br/><br/>"
        f"Статус: <b>{status}</b><br/><br/>"
        "<font size=6>1 – счет-фактура и<br/>передаточный документ (акт)<br/>"
        "2 – передаточный документ<br/>(акт)</font>",
        styles["RuBody"],
    )
    hdr = [
        [
            left,
            Paragraph(
                f"Счет-фактура № <b>{act.document_number}</b> от <b>{doc_date_word}</b> (1)<br/>"
                f"Исправление № — от — (1а)<br/>"
                f"<b>Продавец:</b> {company.name} (2)<br/>"
                f"Адрес: {company.legal_address or '—'} (2а)<br/>"
                f"ИНН/КПП продавца: {comp_inn_kpp} (2б)<br/>"
                f"Грузоотправитель и его адрес: {company.name} (3)<br/>"
                f"К платежно-расчетному документу № — от — (5)<br/>"
                f"Документ об отгрузке: № — от — (5а)",
                styles["RuBody"],
            ),
            Paragraph(
                f"<b>Покупатель:</b> {client.name} (6)<br/>"
                f"Адрес: {client.legal_address or '—'} (6а)<br/>"
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

    # ── ТАБЛИЦА ТОВАРОВ: 3 строки заголовка + официальные графы ──
    W = [6, 9, 96, 8, 7, 9, 11, 14, 16, 10, 8, 14, 16, 7, 9, 12]
    W = [w * mm for w in W]
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
        "Регистрационный номер декларации на товары или регистрационный номер партии товара, подлежащего прослеживаемости",
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
    for item_row in [work]:
        data.append(
            [
                "1",
                "—",
                item_row,
                "—",
                "—",
                "шт",
                "1,000",
                f"{subtotal:,.2f}".replace(",", " "),
                f"{subtotal:,.2f}".replace(",", " "),
                "без акциза",
                f"{vat_rate:.0f}%" if show_vat else "Без НДС",
                f"{vat:,.2f}".replace(",", " ") if show_vat else "—",
                f"{total:,.2f}".replace(",", " "),
                "—",
                "—",
                "—",
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
            f"{subtotal:,.2f}".replace(",", " "),
            "Х",
            f"{vat_rate:.0f}%" if show_vat else "Х",
            f"{vat:,.2f}".replace(",", " ") if show_vat else "Х",
            f"{total:,.2f}".replace(",", " "),
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

    # ── Подписи составителя ──
    story.append(Paragraph("Документ составлен на 1 листе", styles["RuBody"]))
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
    t = Table(sig, colWidths=[138 * mm, 139 * mm])
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

    # ── Блок передачи/получения [8]–[19] (нумерация ред. 2026 г.) ──
    tr = [
        [
            Paragraph(
                f"Основание передачи (сдачи)/ получения (приемки) <b>{basis}</b> [8]<br/>"
                f"<font size=6>(договор; доверенность и др.)</font><br/>"
                f"Данные о транспортировке и грузе: — [9]<br/>"
                f"Товар (груз) передал/ услуги, результаты работ, права сдал [10]:<br/>"
                f"Генеральный директор ______________ (подпись) ______________ (ф.и.о.)<br/>"
                f"Дата отгрузки, передачи (сдачи) «{act.act_date.day}» "
                f"{months[act.act_date.month - 1]} {act.act_date.year} [11]<br/>"
                f"Иные сведения об отгрузке, передаче [12]: —<br/>"
                f"Ответственный за правильность оформления факта хозяйственной жизни [13]:<br/>"
                f"Генеральный директор ______________ (подпись) ______________ (ф.и.о.)<br/>"
                f"Наименование экономического субъекта – составителя документа [14]:<br/>"
                f"{company.name}, ИНН/КПП {comp_inn_kpp}<br/>"
                f"<font size=6>(может не заполняться при проставлении печати в М.П., "
                f"может быть указан ИНН/ КПП)</font><br/>М.П.",
                styles["RuBody"],
            ),
            Paragraph(
                f"Товар (груз) получил/ услуги, результаты работ, права принял [15]:<br/>"
                f"Генеральный директор ______________ (подпись) ______________ (ф.и.о.)<br/>"
                f"Дата получения (приемки) «__» ____________ 20__ года [16]<br/>"
                f"Иные сведения о получении, приемке [17]: —<br/>"
                f"Ответственный за правильность оформления факта хозяйственной жизни [18]:<br/>"
                f"______________ (подпись) ______________ (ф.и.о.)<br/>"
                f"Наименование экономического субъекта – составителя документа [19]:<br/>"
                f"{client.name}, ИНН/КПП {clnt_inn_kpp}<br/>"
                f"<font size=6>(может не заполняться при проставлении печати в М.П., "
                f"может быть указан ИНН/ КПП)</font><br/>М.П.",
                styles["RuBody"],
            ),
        ]
    ]
    t = Table(tr, colWidths=[138 * mm, 139 * mm])
    t.setStyle(_grid())
    story.append(t)
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            f"Всего наименований: 1. Сумма без НДС: {subtotal:.2f} ₽. "
            + (f"НДС {vat_rate:.0f}%: {vat:.2f} ₽. " if show_vat else "НДС: без НДС. ")
            + f"<b>ВСЕГО К ОПЛАТЕ: {total:.2f} ₽</b> ({_money_to_words_ru(total)})",
            styles["RuBody"],
        )
    )
    story.append(
        Paragraph(
            "УПД сгенерирован в системе «СпецТехника Про» • Форма по письму ФНС России от 21.10.2013 "
            "№ ММВ-20-3/96@ в редакции постановления Правительства РФ от 23.01.2026 № 26 "
            "(действует с 01.04.2026)",
            styles["RuSmall"],
        )
    )

    doc.build(story)
    pdf = buf.getvalue()
    logger.info(f"✅ UPD PDF generated via ReportLab: {len(pdf)} bytes")
    return pdf


def generate_torg12_reportlab(
    act, company, client, request=None, driver_name=None, vehicle_plate=None
) -> bytes:
    """ТОРГ-12 по форме ОКУД 0330212 (Постановление Госкомстата РФ от 25.12.1998 № 132)."""
    styles = _styles()
    vat_rate, show_vat, subtotal, vat, total, _ = _calc(act)
    bd_c = getattr(company, "bank_details", None) or {}
    bd_k = getattr(client, "bank_details", None) or {}
    basis = f"Заявка №{act.request_id}" if act.request_id else "—"
    work = getattr(request, "work_type", None) or "Товар по накладной"

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=8 * mm,
        rightMargin=8 * mm,
        topMargin=8 * mm,
        bottomMargin=8 * mm,
    )
    story = []

    # ── Шапка ──
    hdr = [
        [
            Paragraph(
                f"Организация: <b>{company.name}</b> по ОКПО —<br/>"
                f"Структурное подразделение: —<br/>"
                f"Основание: {basis}<br/>"
                f"Товар (груз) передал по доверенности № —",
                styles["RuBody"],
            ),
            Paragraph(
                f"Форма по ОКУД <b>0330212</b><br/>Товарная накладная № <b>{act.document_number}</b><br/>"
                f"Дата составления <b>{act.act_date.strftime('%d.%m.%Y')}</b><br/>"
                f"Утв. Постановлением Госкомстата РФ от 25.12.1998 № 132",
                styles["RuBody"],
            ),
        ]
    ]
    t = Table(hdr, colWidths=[190 * mm, 87 * mm])
    t.setStyle(_grid())
    story.append(t)
    story.append(Spacer(1, 2 * mm))

    # ── Стороны ──
    parties = [
        [
            "Сторона",
            "Организация, адрес, телефон",
            "Банк",
            "Расчетный счет",
            "Корр. счет",
        ],
        [
            "Грузоотправитель",
            f"{company.name}, {company.legal_address or '—'}",
            bd_c.get("bank_name", "—"),
            bd_c.get("account", "—"),
            bd_c.get("correspondent_account", "—"),
        ],
        [
            "Поставщик",
            f"{company.name}, {company.legal_address or '—'}, ИНН/КПП: {company.inn or '—'}/{getattr(company, 'kpp', '') or '—'}",
            bd_c.get("bank_name", "—"),
            bd_c.get("account", "—"),
            bd_c.get("correspondent_account", "—"),
        ],
        [
            "Грузополучатель",
            f"{client.name}, {client.legal_address or '—'}",
            bd_k.get("bank_name", "—"),
            bd_k.get("account", "—"),
            bd_k.get("correspondent_account", "—"),
        ],
        [
            "Плательщик",
            f"{client.name}, {client.legal_address or '—'}, ИНН/КПП: {client.inn or '—'}/{getattr(client, 'kpp', '') or '—'}",
            bd_k.get("bank_name", "—"),
            bd_k.get("account", "—"),
            bd_k.get("correspondent_account", "—"),
        ],
    ]
    t = Table(parties, colWidths=[28 * mm, 92 * mm, 42 * mm, 42 * mm, 40 * mm])
    t.setStyle(
        _grid(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 2 * mm))

    # ── Товары: графы 1–15 ──
    h0 = [
        "№ п/п",
        "Код товара",
        "Наименование и краткое описание товара",
        "Сорт товара",
        "Единица измерения",
        "",
        "Количество",
        "Цена",
        "Сумма",
        "НДС, ставка",
        "НДС, сумма",
        "Сумма с НДС",
        "Кол-во мест",
        "Вид упаковки",
        "Масса нетто/брутто",
    ]
    h1 = [
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
    row = [
        "1",
        "—",
        work,
        "—",
        "—",
        "шт",
        "1.00",
        f"{subtotal:.2f}",
        f"{subtotal:.2f}",
        f"{vat_rate:.0f}%" if show_vat else "Без НДС",
        f"{vat:.2f}" if show_vat else "Х",
        f"{total:.2f}",
        "—",
        "—",
        "—",
    ]
    tot = [
        "Итого",
        "",
        "",
        "",
        "",
        "",
        "1.00",
        "",
        f"{subtotal:.2f}",
        "Х",
        f"{vat:.2f}" if show_vat else "Х",
        f"{total:.2f}",
        "",
        "",
        "",
    ]
    widths = [w * mm for w in [6, 9, 62, 8, 6, 9, 10, 14, 16, 9, 13, 16, 8, 10, 12]]
    t = Table([h0, h1, row, tot], colWidths=widths, repeatRows=2)
    t.setStyle(
        _grid(
            [
                ("SPAN", (4, 0), (5, 0)),
                ("SPAN", (0, 3), (5, 3)),
                ("BACKGROUND", (0, 0), (-1, 1), colors.HexColor("#eeeeee")),
                ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#f5f5f5")),
                ("FONTNAME", (0, 3), (-1, 3), FONT_BOLD),
                ("ALIGN", (0, 1), (-1, 1), "CENTER"),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 2 * mm))

    story.append(
        Paragraph(
            f"Всего наименований 1, мест —, масса нетто —, брутто —<br/>"
            f"<b>Всего сумма прописью:</b> {_money_to_words_ru(total)}",
            styles["RuBody"],
        )
    )
    story.append(Spacer(1, 3 * mm))

    # ── Подписи ──
    sig = [
        [
            Paragraph(
                "Отпуск груза разрешил: Генеральный директор ____________ (подпись) "
                "____________ (ф.и.о.)<br/>"
                "Главный (старший) бухгалтер: ____________ (подпись) ____________ (ф.и.о.)<br/>М.П.",
                styles["RuBody"],
            ),
            Paragraph(
                "Груз принял: Генеральный директор ____________ (подпись) ____________ (ф.и.о.)<br/>"
                "Груз получил (водитель/экспедитор): ____________ (подпись) ____________ (ф.и.о.)"
                + (
                    f"<br/>Водитель: {driver_name}, авто: {vehicle_plate}"
                    if driver_name
                    else ""
                )
                + "<br/>М.П.",
                styles["RuBody"],
            ),
        ]
    ]
    t = Table(sig, colWidths=[138 * mm, 139 * mm])
    t.setStyle(_grid())
    story.append(t)
    story.append(Spacer(1, 2 * mm))
    story.append(
        Paragraph(
            "Товарная накладная (ТОРГ-12) сформирована в системе «СпецТехника Про» • Форма по ОКУД 0330212, "
            "утв. Постановлением Госкомстата РФ от 25.12.1998 № 132 (бумажная форма для внутренней логистики; "
            "электронный документооборот с 01.01.2026 осуществляется посредством УПД)",
            styles["RuSmall"],
        )
    )

    doc.build(story)
    pdf = buf.getvalue()
    logger.info(f"✅ TORG-12 PDF generated via ReportLab: {len(pdf)} bytes")
    return pdf
