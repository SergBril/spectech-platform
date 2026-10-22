"""
Генератор XML УПД по формату ФНС 5.03 (приказ ЕД-7-26/970@ в ред. ЕД-7-26/1032@).

XSD: ON_NSCHFDOP_POW_5_03.xsd (действует с 01.01.2026)
КНД: 1115131
Кодировка: windows-1251
"""

import datetime
import hashlib
import logging
from pathlib import Path
from xml.etree import ElementTree as ET

from lxml import etree

logger = logging.getLogger("spectech.edoxml")

SCHEMAS_DIR = Path(__file__).parent / "schemas"
XSD_FILE = SCHEMAS_DIR / "ON_NSCHFDOP_POW_5_03.xsd"
ENCODING = "windows-1251"


def _generate_id_file(sender_inn: str, receiver_inn: str) -> str:
    now = datetime.datetime.now()
    date_part = now.strftime("%Y%m%d")
    hash_part = hashlib.md5(
        f"{sender_inn}{receiver_inn}{now.isoformat()}".encode()
    ).hexdigest()[:5].upper()
    return f"{receiver_inn}_{sender_inn}_{date_part}_{hash_part}"


def _fmt_date(d: datetime.date) -> str:
    return d.strftime("%d.%m.%Y")


def _fmt_time(dt: datetime.datetime) -> str:
    return dt.strftime("%H.%M.%S")


def _fmt_money(value: float) -> str:
    return f"{value:.2f}"


def _parse_address(addr_str: str) -> dict:
    result = {"КодРегион": "77", "НаимРегион": "г Москва"}
    if not addr_str:
        return result
    parts = addr_str.split(",")
    for part in parts:
        part = part.strip()
        if part[:2].isdigit():
            result["КодРегион"] = part[:2]
        elif any(kw in part.lower() for kw in ["москв", "санкт", "новосиб", "екатерин"]):
            result["НаимРегион"] = part
        elif any(kw in part.lower() for kw in ["ул", "пр", "пер", "пл", "шоссе"]):
            result["Улица"] = part
        elif part.replace(" ", "").replace("-", "").isdigit():
            if "Дом" not in result:
                result["Дом"] = part
            else:
                result["Кварт"] = part
        elif len(part) == 6 and part.isdigit():
            result["Индекс"] = part
    return result


def _add_participant(parent: ET.Element, tag: str, org, is_seller: bool = True):
    elem = ET.SubElement(parent, tag)
    id_sv = ET.SubElement(elem, "ИдСв")
    sv_yul = ET.SubElement(id_sv, "СвЮЛУч")
    sv_yul.set("НаимОрг", getattr(org, "name", "") or "Не указано")
    sv_yul.set("ИННЮЛ", getattr(org, "inn", "") or "0000000000")
    kpp = getattr(org, "kpp", "") or ""
    if kpp:
        sv_yul.set("КПП", kpp)

    legal_addr = getattr(org, "legal_address", "") or ""
    addr_data = _parse_address(legal_addr)
    adr = ET.SubElement(elem, "Адрес")
    adr_rf = ET.SubElement(adr, "АдрРФ")
    adr_rf.set("КодРегион", addr_data.get("КодРегион", "77"))
    adr_rf.set("НаимРегион", addr_data.get("НаимРегион", "г Москва"))
    if addr_data.get("Улица"):
        adr_rf.set("Улица", addr_data["Улица"])
    if addr_data.get("Дом"):
        adr_rf.set("Дом", addr_data["Дом"])
    if addr_data.get("Индекс"):
        adr_rf.set("Индекс", addr_data["Индекс"][:6])

    bank_account = getattr(org, "bank_account", "") or ""
    bik = getattr(org, "bik", "") or ""
    bank_name = getattr(org, "bank_name", "") or ""
    if bank_account or bik:
        bank_rekv = ET.SubElement(elem, "БанкРекв")
        bank_rekv.set("НомерСчета", bank_account)
        if bik or bank_name:
            sv_bank = ET.SubElement(bank_rekv, "СвБанк")
            if bank_name:
                sv_bank.set("НаимБанк", bank_name)
            if bik:
                sv_bank.set("БИК", bik)


def _add_goods_table(doc: ET.Element, items: list, vat_rate: float, show_vat: bool):
    tabl = ET.SubElement(doc, "ТаблСчФакт")
    subtotal_total = 0.0
    vat_total = 0.0
    total_total = 0.0

    valid_rates = ["0%", "5%", "7%", "10%", "18%", "20%", "22%",
                   "9,09%", "16,67%", "18,03%", "5/105", "7/107",
                   "10/110", "18/118", "20/120", "22/122", "без НДС"]

    for idx, item in enumerate(items, start=1):
        sved = ET.SubElement(tabl, "СведТов")
        sved.set("НомСтр", str(idx))
        sved.set("НаимТов", item.get("description", "Работы/услуги"))
        sved.set("ОКЕИ_Тов", "796")
        sved.set("НаимЕдИзм", item.get("unit", "шт"))
        qty = item["quantity"]
        sved.set("КолТов", f"{qty:.11f}".rstrip("0").rstrip(".") or "1")
        sved.set("ЦенаТов", _fmt_money(item["unit_price"]))
        sved.set("СтТовБезНДС", _fmt_money(item["subtotal"]))

        if show_vat:
            rate_str = f"{vat_rate:.0f}%"
            if rate_str not in valid_rates:
                rate_str = "20%"
            sved.set("НалСт", rate_str)
        else:
            sved.set("НалСт", "без НДС")

        sved.set("СтТовУчНал", _fmt_money(item["total"]))

        akciz = ET.SubElement(sved, "Акциз")
        bez_akciz = ET.SubElement(akciz, "БезАкциз")
        bez_akciz.text = "без акциза"

        sum_nal = ET.SubElement(sved, "СумНал")
        if show_vat:
            sn = ET.SubElement(sum_nal, "СумНал")
            sn.text = _fmt_money(item["vat_amount"])
        else:
            bn = ET.SubElement(sum_nal, "БезНДС")
            bn.text = "без НДС"

        subtotal_total += item["subtotal"]
        vat_total += item["vat_amount"]
        total_total += item["total"]

    vsego = ET.SubElement(tabl, "ВсегоОпл")
    vsego.set("СтТовБезНДСВсего", _fmt_money(subtotal_total))
    vsego.set("СтТовУчНалВсего", _fmt_money(total_total))
    sum_nal_vs = ET.SubElement(vsego, "СумНалВсего")
    if show_vat:
        sn_vs = ET.SubElement(sum_nal_vs, "СумНал")
        sn_vs.text = _fmt_money(vat_total)
    else:
        bn_vs = ET.SubElement(sum_nal_vs, "БезНДС")
        bn_vs.text = "без НДС"


def _add_signer(root: ET.Element, company):
    podp = ET.SubElement(root, "Подписант")
    podp.set("СпосПодтПолном", "1")
    podp.set("Должн", getattr(company, "director_position", "Генеральный директор") or "Генеральный директор")
    fio = ET.SubElement(podp, "ФИО")
    director = getattr(company, "director_name", "") or ""
    parts = director.split()
    fio.set("Фамилия", parts[0] if parts else "Иванов")
    fio.set("Имя", parts[1] if len(parts) > 1 else "Иван")
    if len(parts) > 2:
        fio.set("Отчество", " ".join(parts[2:]))


def generate_upd_xml(act, company, client, request=None, items=None) -> bytes:
    now = datetime.datetime.now()
    act_date = getattr(act, "act_date", None) or now.date()
    if isinstance(act_date, datetime.datetime):
        act_date = act_date.date()

    is_osno = getattr(act, "tax_system", "osno") == "osno"
    function = "СЧФДОП" if is_osno else "ДОП"
    vat_rate = float(getattr(act, "vat_rate", 0) or 0)
    if is_osno and vat_rate <= 0:
        vat_rate = 20.0
    show_vat = is_osno

    if not items:
        total = float(getattr(act, "total_amount", 0) or 0)
        if show_vat and vat_rate > 0:
            subtotal = total / (1 + vat_rate / 100)
            vat = total - subtotal
        else:
            subtotal, vat = total, 0.0
        work = getattr(request, "work_type", None) or "Работы по акту"
        items = [{
            "description": work, "unit": "шт", "quantity": 1.0,
            "unit_price": subtotal, "subtotal": subtotal,
            "vat_amount": vat, "total": total,
        }]

    sender_inn = getattr(company, "inn", "") or "0000000000"
    receiver_inn = getattr(client, "inn", "") or "0000000000"

    root = ET.Element("Файл")
    root.set("ИдФайл", _generate_id_file(sender_inn, receiver_inn))
    root.set("ВерсФорм", "5.03")
    root.set("ВерсПрог", "spectech-platform/1.0")

    doc = ET.SubElement(root, "Документ")
    doc.set("КНД", "1115131")
    doc.set("Функция", function)
    doc.set("ДатаИнфПр", _fmt_date(act_date))
    doc.set("ВремИнфПр", _fmt_time(now))
    doc.set("НаимДокОпр", "Универсальный передаточный документ")

    sv_sf = ET.SubElement(doc, "СвСчФакт")
    sv_sf.set("НомерДок", getattr(act, "document_number", "") or str(getattr(act, "id", "1")))
    sv_sf.set("ДатаДок", _fmt_date(act_date))

    _add_participant(sv_sf, "СвПрод", company, is_seller=True)

    gruz_ot = ET.SubElement(sv_sf, "ГрузОт")
    on_zhe = ET.SubElement(gruz_ot, "ОнЖе")
    on_zhe.text = "он же"

    _add_participant(sv_sf, "СвПокуп", client, is_seller=False)

    den_izm = ET.SubElement(sv_sf, "ДенИзм")
    den_izm.set("КодОКВ", "643")
    den_izm.set("НаимОКВ", "Российский рубль")

    _add_goods_table(doc, items, vat_rate, show_vat)

    sv_prod_per = ET.SubElement(doc, "СвПродПер")
    sv_per = ET.SubElement(sv_prod_per, "СвПер")
    sv_per.set("СодОпер", "Реализация")
    sv_per.set("ДатаПер", _fmt_date(act_date))
    bez_dok = ET.SubElement(sv_per, "БезДокОснПер")
    bez_dok.text = "1"

    _add_signer(doc, company)

    xml_bytes = ET.tostring(root, encoding=ENCODING, xml_declaration=True)

    if XSD_FILE.exists():
        try:
            with open(XSD_FILE, "rb") as f:
                schema_doc = etree.parse(f)
            schema = etree.XMLSchema(schema_doc)
            xml_doc = etree.fromstring(xml_bytes)
            is_valid = schema.validate(xml_doc)
            if is_valid:
                logger.info("UPD XML passed XSD validation")
            else:
                errors = [str(e) for e in schema.error_log]
                logger.warning("UPD XML XSD validation warnings: %s", errors[:5])
        except Exception as e:
            logger.warning("XSD validation skipped: %s", e)
    else:
        logger.warning("XSD file not found: %s", XSD_FILE)

    logger.info("UPD XML generated: %d bytes", len(xml_bytes))
    return xml_bytes


def validate_upd_xml(xml_bytes: bytes) -> tuple[bool, list[str]]:
    if not XSD_FILE.exists():
        return False, [f"XSD schema not found: {XSD_FILE}"]
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
