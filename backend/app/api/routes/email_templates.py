"""📧 CRUD endpoints для email-шаблонов."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.email import EmailTemplate
from app.schemas.email import (
    EmailTemplateCreate,
    EmailTemplateRead,
    EmailTemplateUpdate,
)

logger = logging.getLogger("spectech.email_templates")

router = APIRouter(prefix="/email-templates", tags=["📧 Email Templates"])


@router.get(
    "/",
    response_model=list[EmailTemplateRead],
    summary="Список email-шаблонов",
)
def list_email_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    template_type: str | None = Query(None),
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить список email-шаблонов компании."""
    query = select(EmailTemplate).where(EmailTemplate.company_id == company_id)

    if template_type:
        query = query.where(EmailTemplate.template_type == template_type)
    if is_active is not None:
        query = query.where(EmailTemplate.is_active == is_active)

    query = query.order_by(EmailTemplate.created_at.desc()).offset(skip).limit(limit)
    templates = db.scalars(query).all()

    return templates


@router.get(
    "/{template_id}",
    response_model=EmailTemplateRead,
    summary="Детали email-шаблона",
)
def get_email_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить детали email-шаблона."""
    template = (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.id == template_id,
            EmailTemplate.company_id == company_id,
        )
        .first()
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Шаблон не найден",
        )

    return template


@router.post(
    "/",
    response_model=EmailTemplateRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать email-шаблон",
)
def create_email_template(
    payload: EmailTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Создать новый email-шаблон."""
    template = EmailTemplate(
        company_id=company_id,
        name=payload.name,
        template_type=payload.template_type,
        subject=payload.subject,
        html_body=payload.html_body,
        text_body=payload.text_body,
        description=payload.description,
        is_active=payload.is_active,
        is_default=payload.is_default,
    )

    db.add(template)
    db.commit()
    db.refresh(template)

    logger.info(f"Email template created: {template.name} (ID: {template.id})")

    return template


@router.put(
    "/{template_id}",
    response_model=EmailTemplateRead,
    summary="Обновить email-шаблон",
)
def update_email_template(
    template_id: int,
    payload: EmailTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Обновить email-шаблон."""
    template = (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.id == template_id,
            EmailTemplate.company_id == company_id,
        )
        .first()
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Шаблон не найден",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    db.commit()
    db.refresh(template)

    logger.info(f"Email template updated: {template.name} (ID: {template.id})")

    return template


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить email-шаблон",
)
def delete_email_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Удалить email-шаблон."""
    template = (
        db.query(EmailTemplate)
        .filter(
            EmailTemplate.id == template_id,
            EmailTemplate.company_id == company_id,
        )
        .first()
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Шаблон не найден",
        )

    db.delete(template)
    db.commit()

    logger.info(f"Email template deleted: ID {template_id}")

    return None
