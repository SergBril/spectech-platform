"""Модуль admin для shifts router."""

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db

from app.models.auth import User, AuditLog, NotificationTemplate, UserNotificationPreference, UserStatus
from app.services.rbac_service import RBACMiddleware, Role
from app.services.audit_service import log_action
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/audit-logs", summary="📋 Журнал действий пользователей")
def list_audit_logs(
    user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Журнал аудита действий (только для admin)."""
    from app.services.rbac_service import RBACMiddleware
    from app.models.auth import AuditLog
    from sqlalchemy import func

    RBACMiddleware.require(current_user, "audit:read")

    stmt = select(AuditLog)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= date_from)
    if date_to:
        stmt = stmt.where(AuditLog.created_at <= date_to)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    stmt = stmt.order_by(AuditLog.created_at.desc())
    stmt = stmt.offset((page - 1) * per_page).limit(per_page)
    logs = db.execute(stmt).scalars().all()

    items = [{
        "id": l.id, "user_id": l.user_id, "action": l.action,
        "resource_type": l.resource_type, "resource_id": l.resource_id,
        "details": l.details, "ip_address": l.ip_address,
        "created_at": l.created_at.isoformat() if l.created_at else None,
    } for l in logs]

    return {"items": items, "total": total, "page": page, "per_page": per_page}


# === User Role Management ===


@router.get("/users/roles", summary="👥 Список пользователей с ролями", tags=["RBAC"])
def list_users_with_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список всех пользователей с их ролями (admin only)."""
    from app.services.rbac_service import RBACMiddleware
    RBACMiddleware.require(current_user, "users:manage_roles")

    users = db.execute(select(User)).scalars().all()
    return [{
        "id": u.id, "email": u.email, "full_name": u.full_name,
        "role": getattr(u, 'role', 'viewer'),
        "is_superuser": u.is_superuser,
        "status": u.status.value if hasattr(u.status, 'value') else str(u.status),
    } for u in users]



@router.put("/users/{user_id}/role", summary="🔑 Назначить роль пользователю", tags=["RBAC"])
def assign_user_role(
    user_id: int,
    role: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Назначить роль пользователю (admin only)."""
    from app.services.rbac_service import RBACMiddleware, Role
    from app.services.audit_service import log_action

    RBACMiddleware.require(current_user, "users:manage_roles")

    valid_roles = [r.value for r in Role]
    if role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Valid: {valid_roles}")

    target = db.get(User, user_id)
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    old_role = getattr(target, 'role', 'viewer')
    target.role = role
    db.commit()

    log_action(db, current_user.id, "update", "user_role", user_id,
               details=f"Role changed: {old_role} → {role}")

    # Send notifications about role change
    # Send notifications using templates (respect user preferences)
    from app.services.notification_prefs_helper import should_notify

    try:
        if should_notify(db, user_id, "role_change", "email"):
            from app.services.notification_template_service import render_template
            email_tmpl = render_template(db, "role_change", "email", name=target.full_name or target.email, old_role=old_role, new_role=role)
            if email_tmpl and target.email:
                from app.services.email_service import send_email
                send_email(target.email, email_tmpl["subject"], email_tmpl["body"])
    except Exception:
        pass

    try:
        if should_notify(db, user_id, "role_change", "max"):
            from app.services.notification_template_service import render_template
            from app.services.max_messenger_service import max_messenger_service
            import asyncio
            max_tmpl = render_template(db, "role_change", "max", old_role=old_role, new_role=role)
            if max_tmpl:
                loop = asyncio.new_event_loop()
                loop.run_until_complete(max_messenger_service.notify_user(db, user_id, max_tmpl["subject"], max_tmpl["body"]))
                loop.close()
    except Exception:
        pass


    return {"message": f"Роль пользователя {target.full_name or target.email} изменена: {old_role} → {role}"}

# === MAX Messenger Integration ===


@router.post("/users/bulk-role", summary="Bulk role change", tags=["RBAC"])
def bulk_change_roles(
    user_ids: list[int] = Body(...),
    role: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Массовая смена роли для нескольких пользователей (admin only)."""
    from app.services.rbac_service import RBACMiddleware, Role
    from app.services.audit_service import log_action

    RBACMiddleware.require(current_user, "users:manage_roles")

    valid_roles = [r.value for r in Role]
    if role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Valid: {valid_roles}")

    updated = 0
    for uid in user_ids:
        user = db.get(User, uid)
        if user and user.id != current_user.id:
            old_role = getattr(user, "role", "viewer")
            user.role = role
            updated += 1
            log_action(db, current_user.id, "update", "user_role", uid,
                       details=f"Bulk: {old_role} -> {role}")

    db.commit()
    return {"updated": updated, "role": role}



@router.post("/users/import-csv", summary="Import users from CSV", tags=["RBAC"])
async def import_users_csv(
    file: UploadFile = File(...),
    default_role: str = Body(default="viewer"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Импорт пользователей из CSV файла.

    CSV columns: email, full_name, phone, role (optional)
    """
    import csv
    import io
    import secrets
    from app.services.rbac_service import Role
    from app.services.audit_service import log_action
    from app.models.auth import UserStatus

    RBACMiddleware.require(current_user, "users:manage_roles")

    content_bytes = await file.read()
    text = content_bytes.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    created = 0
    skipped = 0
    errors = []

    valid_roles = [r.value for r in Role]

    for row_num, row in enumerate(reader, 2):
        email = (row.get("email") or "").strip()
        if not email:
            errors.append(f"Row {row_num}: missing email")
            continue

        existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing:
            skipped += 1
            continue

        user_role = (row.get("role") or default_role).strip()
        if user_role not in valid_roles:
            user_role = "viewer"

        import hashlib
        temp_password = secrets.token_urlsafe(16)
        password_hash = hashlib.sha256(temp_password.encode()).hexdigest()

        new_user = User(
            email=email,
            full_name=(row.get("full_name") or "").strip() or email,
            phone=(row.get("phone") or "").strip() or None,
            role=user_role,
            password_hash=password_hash,
            status=UserStatus.active if hasattr(UserStatus, "active") else "active",
        )
        db.add(new_user)
        created += 1

    db.commit()
    log_action(db, current_user.id, "create", "user_import", None,
               details=f"CSV import: {created} created, {skipped} skipped")

    return {"created": created, "skipped": skipped, "errors": errors[:10]}



@router.get("/users/export-csv", summary="Export users CSV", tags=["RBAC"])
def export_users_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Экспорт пользователей в CSV (admin only)."""
    import csv
    import io
    from fastapi.responses import StreamingResponse
    from app.services.rbac_service import RBACMiddleware
    RBACMiddleware.require(current_user, "users:manage_roles")

    users = db.execute(select(User)).scalars().all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["email", "full_name", "phone", "role", "status"])
    for u in users:
        writer.writerow([u.email, u.full_name or "", u.phone or "", getattr(u, "role", "viewer"), u.status.value if hasattr(u.status, "value") else str(u.status)])
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="users.csv"'})



@router.get("/audit-logs/role-history/{user_id}", summary="Role change history", tags=["Audit"])
def get_role_history(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """История изменений роли пользователя."""
    from app.models.auth import AuditLog
    logs = db.execute(
        select(AuditLog).where(
            AuditLog.resource_type == "user_role",
            AuditLog.resource_id == user_id,
        ).order_by(AuditLog.created_at.desc())
    ).scalars().all()
    return [{"id": l.id, "action": l.action, "details": l.details, "created_at": l.created_at.isoformat() if l.created_at else None} for l in logs]


# === User Notification Preferences ===


def list_notification_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список шаблонов уведомлений."""
    from app.models.auth import NotificationTemplate
    tmpls = db.execute(select(NotificationTemplate).order_by(NotificationTemplate.code)).scalars().all()
    return [{"id": t.id, "code": t.code, "channel": t.channel, "subject": t.subject, "body": t.body, "is_active": t.is_active} for t in tmpls]



def update_notification_template(
    tmpl_id: int,
    subject: str | None = Body(default=None),
    body: str | None = Body(default=None),
    is_active: bool | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить шаблон уведомления (admin only)."""
    from app.services.rbac_service import RBACMiddleware
    from app.models.auth import NotificationTemplate
    RBACMiddleware.require(current_user, "templates:manage")

    tmpl = db.get(NotificationTemplate, tmpl_id)
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if subject is not None:
        tmpl.subject = subject
    if body is not None:
        tmpl.body = body
    if is_active is not None:
        tmpl.is_active = is_active
    db.commit()
    return {"message": "Template updated"}



def init_defaults(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать стандартные шаблоны уведомлений."""
    from app.services.rbac_service import RBACMiddleware
    from app.services.notification_template_service import init_default_templates
    RBACMiddleware.require(current_user, "templates:manage")
    created = init_default_templates(db)
    return {"created": created}



def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Полный профиль текущего пользователя."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "phone": current_user.phone,
        "role": getattr(current_user, "role", "viewer"),
        "is_superuser": current_user.is_superuser,
        "telegram_id": current_user.telegram_id,
        "max_chat_id": current_user.max_chat_id,
        "max_bound": bool(current_user.max_chat_id),
        "status": current_user.status.value if hasattr(current_user.status, "value") else str(current_user.status),
        "last_login_at": current_user.last_login_at.isoformat() if current_user.last_login_at else None,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
    }



def update_my_profile(
    full_name: str | None = Body(default=None),
    phone: str | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Обновить свой профиль."""
    from app.services.audit_service import log_action
    changes = []
    if full_name is not None and full_name != current_user.full_name:
        current_user.full_name = full_name
        changes.append("full_name")
    if phone is not None and phone != current_user.phone:
        current_user.phone = phone
        changes.append("phone")
    if changes:
        db.commit()
        log_action(db, current_user.id, "update", "profile", current_user.id,
                   details="Updated: " + ", ".join(changes))
    return {"message": "Profile updated", "changes": changes}


# === Notification Templates ===


def get_notification_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.auth import UserNotificationPreference
    prefs = db.execute(
        select(UserNotificationPreference).where(UserNotificationPreference.user_id == current_user.id)
    ).scalar_one_or_none()
    if not prefs:
        return {k: True for k in ["notify_role_change_max", "notify_role_change_email", "notify_overdue_max", "notify_overdue_email", "notify_act_signed_max", "notify_act_signed_email"]}
    return {
        "notify_role_change_max": prefs.notify_role_change_max,
        "notify_role_change_email": prefs.notify_role_change_email,
        "notify_overdue_max": prefs.notify_overdue_max,
        "notify_overdue_email": prefs.notify_overdue_email,
        "notify_act_signed_max": prefs.notify_act_signed_max,
        "notify_act_signed_email": prefs.notify_act_signed_email,
    }



def update_notification_settings(
    notify_role_change_max: bool | None = Body(default=None),
    notify_role_change_email: bool | None = Body(default=None),
    notify_overdue_max: bool | None = Body(default=None),
    notify_overdue_email: bool | None = Body(default=None),
    notify_act_signed_max: bool | None = Body(default=None),
    notify_act_signed_email: bool | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.auth import UserNotificationPreference
    prefs = db.execute(
        select(UserNotificationPreference).where(UserNotificationPreference.user_id == current_user.id)
    ).scalar_one_or_none()
    if not prefs:
        prefs = UserNotificationPreference(user_id=current_user.id)
        db.add(prefs)
    if notify_role_change_max is not None: prefs.notify_role_change_max = notify_role_change_max
    if notify_role_change_email is not None: prefs.notify_role_change_email = notify_role_change_email
    if notify_overdue_max is not None: prefs.notify_overdue_max = notify_overdue_max
    if notify_overdue_email is not None: prefs.notify_overdue_email = notify_overdue_email
    if notify_act_signed_max is not None: prefs.notify_act_signed_max = notify_act_signed_max
    if notify_act_signed_email is not None: prefs.notify_act_signed_email = notify_act_signed_email
    db.commit()
    return {"message": "Notification settings updated"}



