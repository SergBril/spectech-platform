"""Набор компаний для системных задач не должен зависеть от user_companies."""

from app.models.company import Company
from app.tasks.scheduler import _active_company_ids


def test_company_without_user_links_is_included(db_session):
    """Активная компания без строк в user_companies всё равно обрабатывается.

    UserCompany - fallback в get_user_company_ids: у обычного пользователя
    компания берётся из users.company_id. Опора на user_companies оставляла
    такие компании без алертов, проверки ТО и разноски платежей - молча.
    """
    c = Company(name="ООО Без связей", inn="7700000001", is_active=True)
    db_session.add(c)
    db_session.commit()

    assert c.id in _active_company_ids(db_session)


def test_inactive_company_is_excluded(db_session):
    c = Company(name="ООО Закрытая", inn="7700000002", is_active=False)
    db_session.add(c)
    db_session.commit()

    assert c.id not in _active_company_ids(db_session)


def test_every_active_company_appears_exactly_once(db_session):
    for inn in ("7700000003", "7700000004"):
        db_session.add(Company(name=f"ООО {inn}", inn=inn, is_active=True))
    db_session.commit()

    ids = _active_company_ids(db_session)
    assert len(ids) == len(set(ids))
    assert set(ids) == {
        c.id
        for c in db_session.query(Company).filter(Company.is_active.is_(True)).all()
    }
