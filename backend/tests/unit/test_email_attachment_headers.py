"""Заголовки вложений: кириллическое имя и битый PDF давали SMTP 550.

mail.ru отвечал 550 invalid headers на письма с кириллическим именем вложения:
encoded-word внутри параметра filename= RFC-невалиден, нужен filename* по RFC 2231.
Проверка размера PDF была только в одной обёртке из нескольких.
"""

from email.mime.multipart import MIMEMultipart

from app.services.email_service import email_service


def test_cyrillic_filename_uses_rfc2231():
    msg = MIMEMultipart()
    email_service._attach_file(msg, "АКТ-002.pdf", b"%PDF-1.4 " + b"x" * 200)
    part = msg.get_payload()[0]
    disposition = part.get("Content-Disposition")
    assert "filename*=" in disposition, f"нет RFC 2231: {disposition}"
    assert "=?utf-8?" not in disposition, f"encoded-word в filename=: {disposition}"
    assert part.get_filename() == "АКТ-002.pdf", "имя файла не восстанавливается"


def test_tiny_pdf_is_not_attached():
    msg = MIMEMultipart()
    email_service._attach_file(msg, "broken.pdf", b"%PDF-1.4")
    assert msg.get_payload() == [], "битый PDF приложен: письмо получит 550"


def test_valid_pdf_is_attached():
    msg = MIMEMultipart()
    email_service._attach_file(msg, "ok.pdf", b"%PDF-1.4 " + b"x" * 200)
    assert len(msg.get_payload()) == 1
