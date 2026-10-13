"""API для карты техники."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from app.api.deps import get_current_company_id, get_current_user
from app.core.db import get_db
from app.models.auth import User
from app.models.telematics import GpsPoint
from app.models.catalog import Vehicle
from app.services.gps_providers.factory import get_available_providers, create_gps_adapter

router = APIRouter()


@router.get("/vehicles/positions")
def get_vehicle_positions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """📍 Последние позиции всей техники компании."""
    # Получаем все vehicles компании
    vehicles = db.query(Vehicle).filter(Vehicle.company_id == company_id).all()
    
    positions = []
    for v in vehicles:
        # Последняя GPS точка для каждого vehicle
        last_point = (
            db.query(GpsPoint)
            .filter(GpsPoint.vehicle_id == v.id)
            .order_by(desc(GpsPoint.recorded_at))
            .first()
        )
        
        if last_point:
            positions.append({
                "vehicle_id": v.id,
                "vehicle_name": v.name or f"Vehicle #{v.id}",
                "vehicle_type": getattr(v, 'type', None),
                "status": getattr(v, 'status', None),
                "latitude": last_point.latitude,
                "longitude": last_point.longitude,
                "speed": last_point.speed,
                "heading": last_point.heading,
                "engine_on": last_point.engine_on,
                "fuel_level": last_point.fuel_level,
                "altitude": last_point.altitude,
                "recorded_at": last_point.recorded_at.isoformat() if last_point.recorded_at else None,
            })
    
    return {"positions": positions}


@router.get("/vehicles/{vehicle_id}/track")
def get_vehicle_track(
    vehicle_id: int,
    date_from: str = Query(..., description="Начало периода (ISO format)"),
    date_to: str = Query(..., description="Конец периода (ISO format)"),
    limit: int = Query(default=1000, ge=1, le=10000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """🛤️ Маршрут техники за выбранный период."""
    dt_from = datetime.fromisoformat(date_from.replace("Z", "+00:00"))
    dt_to = datetime.fromisoformat(date_to.replace("Z", "+00:00"))
    
    # Проверяем что vehicle принадлежит компании
    vehicle = db.query(Vehicle).filter(
        Vehicle.id == vehicle_id,
        Vehicle.company_id == company_id,
    ).first()
    
    if not vehicle:
        return {"points": [], "vehicle_name": None}
    
    points = (
        db.query(GpsPoint)
        .filter(
            GpsPoint.vehicle_id == vehicle_id,
            GpsPoint.recorded_at >= dt_from,
            GpsPoint.recorded_at <= dt_to,
        )
        .order_by(GpsPoint.recorded_at.asc())
        .limit(limit)
        .all()
    )
    
    return {
        "vehicle_id": vehicle_id,
        "vehicle_name": vehicle.name or f"Vehicle #{vehicle_id}",
        "points": [
            {
                "latitude": p.latitude,
                "longitude": p.longitude,
                "speed": p.speed,
                "heading": p.heading,
                "engine_on": p.engine_on,
                "fuel_level": p.fuel_level,
                "recorded_at": p.recorded_at.isoformat() if p.recorded_at else None,
            }
            for p in points
        ],
    }


@router.get("/geofences")
def get_geofences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    company_id: int = Depends(get_current_company_id),
):
    """🔲 Список геозон компании."""
    from app.models.telematics import Geofence
    
    geofences = db.query(Geofence).filter(
        Geofence.company_id == company_id
    ).all()
    
    return {
        "geofences": [
            {
                "id": g.id,
                "name": g.name,
                "type": g.type.value if hasattr(g.type, 'value') else g.type,
                "coordinates": g.coordinates if hasattr(g, 'coordinates') else None,
                "radius": g.radius if hasattr(g, 'radius') else None,
            }
            for g in geofences
        ]
    }



@router.get("/providers")
def list_gps_providers(
    current_user: User = Depends(get_current_user),
):
    """📡 Список доступных GPS-провайдеров."""
    return {"providers": get_available_providers()}


@router.post("/providers/test")
async def test_gps_provider(
    provider: str = Query(...),
    config: dict = Body(...),
    current_user: User = Depends(get_current_user),
):
    """🔌 Проверить соединение с GPS-провайдером."""
    try:
        adapter = create_gps_adapter(provider, config)
        ok = await adapter.test_connection()
        return {"success": ok, "provider": provider}
    except Exception as e:
        return {"success": False, "provider": provider, "error": str(e)}

@router.post("/providers/request")
def request_new_provider(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """📨 Запрос на добавление нового GPS-провайдера."""
    from app.models.telematics import Notification

    provider_name = payload.get("provider_name", "").strip()
    if not provider_name:
        raise HTTPException(status_code=400, detail="Укажите название провайдера")

    notification = Notification(
        user_id=current_user.id,
        channel="system",
        title=f"Запрос нового GPS-провайдера: {provider_name}",
        body=(
            f"Пользователь {current_user.email} запросил добавление GPS-провайдера.\n"
            f"Название: {provider_name}\n"
            f"URL: {payload.get('provider_url', '—')}\n"
            f"Комментарий: {payload.get('comment', '—')}"
        ),
        is_read=False,
    )
    db.add(notification)
    db.commit()

    logger.info(f"📨 New GPS provider request: {provider_name} from user #{current_user.id}")
    return {"message": "Заявка отправлена"}