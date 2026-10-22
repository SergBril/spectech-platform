"""Сервис шаблонов уведомлений."""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.auth import NotificationTemplate

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATES = {
    "role_change": {
        "max": {"subject": "Смена роли", "body": "Ваша роль изменена: {old_role} -> {new_role}"},
        "email": {"subject": "Spectech: Ваша роль изменена", "body": "Здравствуйте, {name}!\n\nВаша роль изменена: {old_role} -> {new_role}\n\n— Команда Spectech"},
        "fcm": {"subject": "Смена роли", "body": "Роль изменена: {old_role} -> {new_role}"},
    },
    "overdue_acts": {
        "max": {"subject": "Просроченные акты", "body": "{count} просроченных актов на сумму {amount} RUB"},
        "email": {"subject": "Spectech: Просроченные платежи", "body": "У вас {count} просроченных актов на сумму {amount} RUB.\n\n— Команда Spectech"},
        "fcm": {"subject": "Просроченные платежи", "body": "{count} актов на {amount} RUB"},
    },
    "act_signed": {
        "max": {"subject": "Акт подписан", "body": "Акт {act_number} подписан контрагентом"},
        "email": {"subject": "Spectech: Акт подписан", "body": "Акт {act_number} подписан контрагентом.\n\n— Команда Spectech"},
        "fcm": {"subject": "Акт подписан", "body": "Акт {act_number} подписан"},
    },
    "act_rejected": {
        "max": {"subject": "Акт отклонён", "body": "Акт {act_number} ОТКЛОНЁН контрагентом"},
        "email": {"subject": "Spectech: Акт отклонён", "body": "Акт {act_number} отклонён контрагентом.\n\n— Команда Spectech"},
        "fcm": {"subject": "Акт отклонён", "body": "Акт {act_number} отклонён"},
    },
}


def render_template(db: Session, code: str, channel: str, **kwargs) -> dict | None:
    """Render notification template with variables."""
    tmpl = db.execute(
        select(NotificationTemplate).where(
            NotificationTemplate.code == code,
            NotificationTemplate.channel == channel,
            NotificationTemplate.is_active == True,
        )
    ).scalar_one_or_none()

    if tmpl:
        try:
            body = tmpl.body.format(**kwargs)
            subject = tmpl.subject.format(**kwargs) if tmpl.subject else ""
            return {"subject": subject, "body": body}
        except KeyError as e:
            logger.warning("Template %s/%s missing variable: %s", code, channel, e)

    # Fallback to defaults
    default = DEFAULT_TEMPLATES.get(code, {}).get(channel)
    if default:
        try:
            return {
                "subject": default["subject"].format(**kwargs),
                "body": default["body"].format(**kwargs),
            }
        except KeyError:
            return {"subject": default["subject"], "body": default["body"]}

    return None


def init_default_templates(db: Session) -> int:
    """Create default notification templates if they don't exist."""
    created = 0
    for code, channels in DEFAULT_TEMPLATES.items():
        for channel, data in channels.items():
            existing = db.execute(
                select(NotificationTemplate).where(
                    NotificationTemplate.code == code,
                    NotificationTemplate.channel == channel,
                )
            ).scalar_one_or_none()
            if not existing:
                tmpl = NotificationTemplate(
                    code=code, channel=channel,
                    subject=data["subject"], body=data["body"],
                )
                db.add(tmpl)
                created += 1
    db.commit()
    if created > 0:
        logger.info("Created %d default notification templates", created)
    return created
