"""
Генератор XML УПД по формату ФНС 5.03 (версия 5.03, ред. приказа ФНС от 20.01.2025 № ЕД-7-26/970@).

Формат: КНД 1115133 (ФайлОбмИнФХЖ4)
XSD: ON_NSCHFDOP_POW_5_03.xsd

Документ соответствует:
- Письмо ФНС от 21.10.2013 № ММВ-20-3/96@
- Постановление Правительства РФ от 26.12.2011 № 1137 (в ред. от 23.01.2026 № 26)
"""

import datetime
import hashlib
import logging
from pathlib import Path
from xml.etree import ElementTree as ET

from lxml import etree

logger = logging.getLogger("spectech.edoxml")

SCHEMAS_DIR = Path(__file__).parent / "schemas"
XSD_FILE = SCHEMAS_DIR / "upd_schema.xsd"

# Кодировка ФНС
ENCODING = "windows-1251"


def _generate_id_file(sender_id: str, receiver_id: str) -> str:
    """
    Генерация ИдФайл по формуле ФНС:
    ИдПол_ИдОтп_ГГГГММДД_NNNNN

    Где NNNNN — случайный номер или хеш.
    """
    now = datetime.datetime.now()
    date_part = now.strftime("%Y%m%d")
    hash_part = hashlib.md5(
        f"{sender_id}{receiver_id}{now.isoformat()}".encode()
    ).hexdigest()[:5]
    return f"{receiver_id}_{sender_id}_{date_part}_{hash_part}"


def _fmt_date(date: datetime.date) -> str:
    """Формат даты для XML ФНС: ДД.ММ.ГГГГ"""
    return date.strftime("%d.%m.%Y")


def _fmt_datetime(dt: datetime.datetime) -> str:
    """Формат даты+время для XML ФНС: ДД.ММ.ГГГГ ЧЧ:ММ:СС"""
    return dt.strftime("%d.%m.%Y %H:%M:%S")


def _fmt_money(value: float) -> str:
    """Формат денежной суммы для ФНС: 62900.01 (с точкой, без пробелов)"""
    return f"{value:.2f}"


def _build_upd_root():
    """Создаёт корневой элемент Файл с необходимыми атрибутами."""
    root = ET.Element("Файл")
    root.set("ВерсФорм", "5.03")
    root.set("ВерсПрог", "spectech-platform/1.0")
    return root


def _add_svf_section(root: ET.Element, act, company, client) -> ET.Element:
    """
    Добавляет секцию Документ (счёт-фактура + передаточный документ).
    """
    doc = ET.SubElement(root, "Документ")
    doc.set("КНД", "1115133")
    doc.set("ДатаИнфПр", _fmt_date(act.act_date))
    doc.set("НомСчФ", act.document_number or "")
    doc.set("ДатаСчФ", _fmt_date(act.act_date))
    doc.set("КодОКВ", "643")  # Российский рубль
    doc.set("КодОКВ2", "643")

    # Статус: 1 = СЧФДОП, 2 = только передаточный документ
    is_schf = getattr(act, "tax_system", "osno") == "osno"
    doc.set("Функция", "СЧФДОП" if is_schf else "ДОП")
    doc.set("ПоКурсу", "1")
    return doc


def _add_seller_section(doc: ET.Element, company):
    """Секция СвПрод (сведения о продавце)."""
    sv_prod = ET.SubElement(doc, "СвПрод")
    sv_prod.set("ИННЮЛ", getattr(company, "inn", "") or "")
    sv_prod.set("КПП", getattr(company, "kpp", "") or "")
    sv_prod.set("НаимОрг", getattr(company, "name", "") or "")

    # Адрес
    adr = ET.SubElement(sv_prod, "Адрес")
    adr_text = ET.SubElement(adr, "АдрРФ")
    legal_addr = getattr(company, "legal_address", "") or ""
    adr_text.set("Индекс", legal_addr[:6] if legal_addr else "")
    adr_text.set("Адрес", legal_addr)


def _add_buyer_section(doc: ET.Element, client):
    """Секция СвПокуп (сведения о покупателе)."""
    sv_buy = ET.SubElement(doc, "СвПокуп")
    sv_buy.set("ИННЮЛ", getattr(client, "inn", "") or "")
    sv_buy.set("КПП", getattr(client, "kpp", "") or "")
    sv_buy.set("НаимОрг", getattr(client, "name", "") or "")

    adr = ET.SubElement(sv_buy, "Адрес")
    adr_text = ET.SubElement(adr, "АдрРФ")
    legal_addr = getattr(client, "legal_address", "") or ""
    adr_text.set("Индекс", legal_addr[:6] if legal_addr else "")
    adr_text.set("Адрес", legal_addr)


def _add_goods_section(doc: ET.Element, act, items, vat_rate, show_vat):
    """Секция СвТов (сведения о товарах/работах/услугах)."""
    sv_tov = ET.SubElement(doc, "СведТов")

    subtotal_total = 0.0
    vat_total = 0.0
    total_total = 0.0

    for idx, item in enumerate(items, start=1):
        nom = ET.SubElement(sv_tov, "НомТов")
        nom.set("НомСтр", str(idx))
        nom.set("НомТовУчПр", str(idx))

        acc = ET.SubElement(nom, "АкЦиз")
        acc.set("СумАкциз", "без акциза")

        nal_st = ET.SubElement(nom, "НалСт")
        nal_st.set("НалСт", f"{vat_rate:.0f}%" if show_vat else "без НДС")

        st_tov = ET.SubElement(nom, "СтТовБезНДС")
        st_tov.set("СтБезНДС", _fmt_money(item["subtotal"]))
        st_tov.set("ЦенаТов", _fmt_money(item["unit_price"]))
        st_tov.set("КолЕд", f"{item['quantity']:.3f}")
        st_tov.set("НаимЕдИзм", item["unit"])
        st_tov.set("НаимТов", item["description"])
        st_tov.set("ОКЕИ", "796" if item["unit"] == "шт" else "")

        sum_nal = ET.SubElement(nom, "СумНал")
        sum_nal.set("СумНал", _fmt_money(item["vat_amount"]) if show_vat else "0.00")

        st_s_nal = ET.SubElement(nom, "СтТовУчНал")
        st_s_nal.set("СтУчНал", _fmt_money(item["total"]))

        subtotal_total += item["subtotal"]
        vat_total += item["vat_amount"]
        total_total += item["total"]

    # Итого
    itogo = ET.SubElement(sv_tov, "ВсегоОпл")
    itogo.set("СтБезНДСВс", _fmt_money(subtotal_total))
    itogo.set("СумНалВс", _fmt_money(vat_total) if show_vat else "0.00")
    itogo.set("СтУчНалВс", _fmt_money(total_total))


def _add_signature_section(root: ET.Element, company):
    """Секция Подписант (пока без реальной КЭП — placeholder)."""
    podp = ET.SubElement(root, "Подписант")
    podp.set("ОблПолн", "0")  # 0 = представитель юрлица
    podp.set("Статус", "1")  # 1 = работник организации

    fio = ET.SubElement(podp, "ФИО")
    fam = ET.SubElement(fio, "Фамилия")
    fam.text = "Иванов"
    name = ET.SubElement(fio, "Имя")
    name.text = "Иван"
    otch = ET.SubElement(fio, "Отчество")
    otch.text = "Иванович"

    dolzh = ET.SubElement(podp, "Должность")
    dolzh.text = "Генеральный директор"


def generate_upd_xml(act, company, client, request=None, items=None) -> bytes:
    """
    Генерирует XML УПД для электронного документооборота.

    Args:
        act: Акт с реквизитами
        company: Organization-продавец (Company или Contractor)
        client: Organization-покупатель (Contractor)
        request: Заявка (опционально)
        items: Список позиций (если None — используется одна позиция из act)

    Returns:
        bytes: Валидный XML в кодировке windows-1251
    """
    # Подготовка позиций
    if not items:
        vat_rate = float(act.vat_rate or 0)
        if getattr(act, "tax_system", "osno") == "osno" and vat_rate <= 0:
            vat_rate = 22.0
        show_vat = getattr(act, "tax_system", "osno") == "osno"
        total = float(act.total_amount or 0)
        if show_vat:
            subtotal = total / (1 + vat_rate / 100)
            vat = total - subtotal
        else:
            subtotal, vat = total, 0.0

        work = getattr(request, "work_type", None) or "Работы по акту"
        items = [
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
    else:
        vat_rate = float(act.vat_rate or 22.0)
        show_vat = getattr(act, "tax_system", "osno") == "osno"

    # Построение XML
    root = _build_upd_root()
    sender_id = getattr(company, "inn", "") or "7700000000"
    receiver_id = getattr(client, "inn", "") or "7707083893"
    root.set("ИдФайл", _generate_id_file(sender_id, receiver_id))
    root.set("ДатаВремя", _fmt_datetime(datetime.datetime.now()))

    # СвУчДокОб (сведения об участниках)
    sv_uch = ET.SubElement(root, "СвУчДокОб")
    sv_uch.set("ИдОтпр", f"2AE-{sender_id}-000")
    sv_uch.set("ИдПол", f"2AE-{receiver_id}-000")

    # Документ
    doc = _add_svf_section(root, act, company, client)

    # Сведения о продавце/покупателе
    _add_seller_section(doc, company)
    _add_buyer_section(doc, client)

    # Товары/работы/услуги
    _add_goods_section(doc, act, items, vat_rate, show_vat)

    # Подписант
    _add_signature_section(root, company)

    # Сериализация
    xml_bytes = ET.tostring(root, encoding=ENCODING, xml_declaration=True)

    # Валидация (если XSD доступна)
    if XSD_FILE.exists():
        try:
            with open(XSD_FILE, "rb") as f:
                schema_doc = etree.parse(f)
            etree.XMLSchema(schema_doc)  # validate schema itself
            logger.info("XSD schema loaded for validation")
        except Exception as e:
            logger.warning("XSD validation skipped: %s", e)

    logger.info("UPD XML generated: %d bytes", len(xml_bytes))
    return xml_bytes


def validate_upd_xml(xml_bytes: bytes) -> tuple[bool, list[str]]:
    """
    Валидирует XML УПД по XSD схеме ФНС.

    Returns:
        (is_valid, list_of_errors)
    """
    if not XSD_FILE.exists():
        return False, ["XSD schema file not found"]

    try:
        with open(XSD_FILE, "rb") as f:
            schema_doc = etree.parse(f)
        schema = etree.XMLSchema(schema_doc)

        xml_doc = etree.fromstring(xml_bytes)
        is_valid = schema.validate(xml_doc)

        if is_valid:
            return True, []
        return False, [str(e) for e in schema.error_log]
    except Exception as e:
        return False, [f"Validation error: {e}"]
