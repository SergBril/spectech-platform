"""Модуль chat для shifts router."""

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, File, HTTPException, Query, Body, UploadFile
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.core.db import get_db

from app.models.chat import ChatMessage, RequestChat
from app.models.catalog import Vehicle
from app.models.shift import ShiftTask
from app.models.contractor import DriverProfile, Employee
from app.models.user_company import UserCompany
from app.services.chat_service import send_chat_message
from app.api.deps import get_current_company_id, get_current_user

from datetime import UTC, datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.core.db import get_db
from app.models.auth import User
from app.models.chat import ChatMessage, RequestChat
from app.models.catalog import Vehicle
from app.models.shift import ShiftTask
from app.models.contractor import DriverProfile, Employee
from app.models.user_company import UserCompany
from app.services.chat_service import send_chat_message
from app.api.deps import get_current_company_id, get_current_user

router = APIRouter()

def get_shift_messages(
    task_id: int,
    limit: int = Query(default=50),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Получить сообщения чата между диспетчером и водителем по смене."""
    from app.models.chat import ChatMessage, RequestChat

    task = db.get(ShiftTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Shift task not found")

    vehicle = db.get(Vehicle, task.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    rooms = db.execute(
        select(RequestChat).where(RequestChat.request_id == task_id)
    ).scalars().all()

    if not rooms:
        return []

    room_ids = [r.id for r in rooms]
    messages = db.execute(
        select(ChatMessage)
        .where(ChatMessage.room_id.in_(room_ids))
        .order_by(ChatMessage.sent_at.desc())
        .limit(limit)
        .offset(offset)
    ).scalars().all()

    result = []
    for m in reversed(messages):
        sender = db.get(User, m.sender_id)
        result.append({
            "id": m.id,
            "sender_id": m.sender_id,
            "sender_name": sender.email if sender else "",
            "text": m.text,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None,
            "is_mine": m.sender_id == current_user.id,
        })
    return result



async def send_shift_message(
    task_id: int,
    text: str = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """Отправить сообщение в чат по смене."""
    from app.services.chat_service import send_chat_message

    task = db.get(ShiftTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Shift task not found")

    vehicle = db.get(Vehicle, task.vehicle_id)
    if not vehicle or vehicle.company_id != company_id:
        raise HTTPException(status_code=403, detail="Access denied")

    # Determine recipient: if current user is dispatcher → send to driver, else → send to dispatcher
    from app.models.contractor import DriverProfile, Employee
    my_profile = db.execute(
        select(DriverProfile).join(Employee, DriverProfile.employee_contractor_id == Employee.contractor_id)
        .where(Employee.user_id == current_user.id)
    ).scalar_one_or_none()

    if my_profile and task.operator_id == my_profile.employee_contractor_id:
        # Driver sending to dispatcher (first company user)
        from app.models.user_company import UserCompany
        dispatcher_id = db.execute(
            select(UserCompany.user_id).where(UserCompany.company_id == company_id)
            .where(UserCompany.user_id != current_user.id)
        ).scalars().first()
        if not dispatcher_id:
            raise HTTPException(status_code=404, detail="No dispatcher found")
        recipient_id = dispatcher_id
    else:
        # Dispatcher sending to driver
        if not task.operator_id:
            raise HTTPException(status_code=400, detail="No driver assigned to shift")
        driver_emp = db.get(Employee, task.operator_id)
        if not driver_emp or not driver_emp.user_id:
            raise HTTPException(status_code=404, detail="Driver has no user account")
        recipient_id = driver_emp.user_id

    result = await send_chat_message(db, current_user.id, recipient_id, text, shift_task_id=task_id)

    # WS broadcast
    try:
        from app.services.websocket_manager import manager
        await manager.broadcast_to_company(company_id, {
            "type": "chat_message",
            "task_id": task_id,
            "sender_id": current_user.id,
            "text": text,
            "sent_at": result.get("sent_at"),
        })
    except Exception:
        pass

    # FCM push to recipient
    try:
        from app.services.fcm_service import fcm_service
        sender_name = current_user.email.split("@")[0]
        preview = text[:50] + ("..." if len(text) > 50 else "")
        await fcm_service.send_to_user(
            recipient_id, f"💬 {sender_name}",
            preview,
            data={"type": "chat_message", "task_id": str(task_id)},
            db=db,
        )
    except Exception:
        pass

    return result



