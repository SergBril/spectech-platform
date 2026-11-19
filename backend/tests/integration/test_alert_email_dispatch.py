"""Email-оповещения диспетчерам: запрос должен исполняться, а не падать тихо.

alert_service фильтровал по User.is_active - такого поля у User нет (есть
status: UserStatus). AttributeError глотался try/except, задача рапортовала успех,
письма не уходили. Существующие тесты мокали send_alert_email целиком, поэтому
запрос не исполнялся ни разу и дефект был невидим.
"""

import pytest


@pytest.mark.asyncio
async def test_dispatcher_receives_the_alert_email(
    db_session, company, sample_user, monkeypatch
):
    from app.models.user_company import UserCompany
    from app.services.alert_service import send_alert_email

    db_session.add(UserCompany(user_id=sample_user.id, company_id=company.id))
    db_session.commit()

    sent = []
    from app.services.email_service import EmailService

    monkeypatch.setattr(
        EmailService,
        "send_email",
        lambda self, **kw: sent.append(kw),
    )

    await send_alert_email(
        company.id, "Просрочено ТО", "Экскаватор CAT 320D", db_session
    )

    assert sent, "письмо диспетчеру не отправлено - запрос получателей упал или пуст"
    assert sample_user.email in [m.get("to_email") for m in sent]


@pytest.mark.asyncio
async def test_suspended_user_is_not_notified(
    db_session, company, sample_user, monkeypatch
):
    from app.models.auth import UserStatus
    from app.models.user_company import UserCompany
    from app.services.alert_service import send_alert_email
    from app.services.email_service import EmailService

    sample_user.status = UserStatus.suspended
    db_session.add(UserCompany(user_id=sample_user.id, company_id=company.id))
    db_session.commit()

    sent = []
    monkeypatch.setattr(EmailService, "send_email", lambda self, **kw: sent.append(kw))

    await send_alert_email(company.id, "Просрочено ТО", "тело", db_session)

    assert not sent, "отключённый пользователь не должен получать оповещения"
