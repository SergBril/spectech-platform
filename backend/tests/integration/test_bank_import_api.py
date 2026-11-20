"""Публикация import_bank_payments (shifts/bank.py).

Маршрут не был опубликован (без декоратора -> 404), хотя сервис импорта починен.
Опубликован по форме сервиса (file + format), доступ по образцу соседней
upload_bank_statement: get_current_user + get_current_company_id. Вызова импорта
во фронтенде нет - путь /shifts/bank/import назначен по конвенции соседних ручек.
"""

from app.core.config import settings

OUR_ACCOUNT = getattr(settings, "BANK_ACCOUNT_NUMBER", "40702810210001399360")
CSV = (
    "Номер,Дата,ИННПлательщика,Плательщик,СчетПлательщика,"
    "ИННПолучателя,Получатель,СчетПолучателя,Сумма,Назначение\n"
    "501,06.11.2026,7701234567,ООО Клиент,40702810000000001234,"
    f"7700000000,Test Company,{OUR_ACCOUNT},50000,Оплата по акту"
)


def _post_import(client, csv=CSV, filename="test.csv"):
    return client.post(
        "/api/v1/shifts/bank/import",
        files={"file": (filename, csv.encode("utf-8"), "text/csv")},
    )


def test_csv_import_creates_records(auth_client, db_session, company):
    from app.models.bank_statement import BankTransaction

    r = _post_import(auth_client)
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1
    tx = (
        db_session.query(BankTransaction)
        .filter(BankTransaction.company_id == company.id)
        .one()
    )
    assert tx.direction == "incoming"
    assert tx.document_number == "501"
    assert tx.counterparty_name == "ООО Клиент"
    assert tx.statement_id is not None


def test_import_requires_auth(client, db_session):
    r = _post_import(client)
    assert r.status_code == 401


def test_import_scoped_to_caller_company(auth_client, db_session, company):
    from app.models.auth import User
    from app.models.bank_statement import BankTransaction
    from app.models.company import Company
    from app.services.auth_service import create_access_token

    # positive control: своя компания -> запись в своей компании
    r = _post_import(auth_client)
    assert r.status_code == 200, r.text
    assert (
        db_session.query(BankTransaction)
        .filter(BankTransaction.company_id == company.id)
        .count()
        == 1
    )

    # чужая компания со своим пользователем
    other = Company(name="Чужая компания", inn="9901234567")
    db_session.add(other)
    db_session.commit()
    db_session.refresh(other)
    other_user = User(
        email="other@example.com",
        full_name="Other User",
        password_hash="other_hashed_password_12345",
        company_id=other.id,
        is_superuser=False,
        status="active",
        failed_login_attempts=0,
    )
    db_session.add(other_user)
    db_session.commit()
    db_session.refresh(other_user)

    token = create_access_token(user=other_user)
    auth_client.headers.update({"Authorization": f"Bearer {token}"})
    r2 = _post_import(auth_client, csv=CSV.replace("501", "502"))
    assert r2.status_code == 200, r2.text

    # запись чужой компании легла в её компанию, а не в нашу
    other_tx = (
        db_session.query(BankTransaction)
        .filter(BankTransaction.company_id == other.id)
        .all()
    )
    assert len(other_tx) == 1
    assert other_tx[0].document_number == "502"
    assert (
        db_session.query(BankTransaction)
        .filter(BankTransaction.company_id == company.id)
        .count()
        == 1
    ), "наша компания не должна получить чужую запись"
