"""Автоматическое логирование действий через декоратор."""
import functools
import logging
from fastapi import Request
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def audit_log(action: str, resource_type: str | None = None):
    """Декоратор для автоматического логирования действий в аудит-лог.
    
    Usage:
        @router.post("/vehicles")
        @audit_log("create", "vehicle")
        def create_vehicle(...):
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs) if hasattr(func, '__wrapped__') or 'async' in str(type(func)) else func(*args, **kwargs)
            
            # Extract db and user from kwargs
            db = kwargs.get('db')
            current_user = kwargs.get('current_user')
            request = kwargs.get('request')
            
            if db and current_user:
                try:
                    from app.services.audit_service import log_action
                    ip = request.client.host if request and hasattr(request, 'client') else None
                    resource_id = None
                    if isinstance(result, dict) and 'id' in result:
                        resource_id = result['id']
                    
                    log_action(
                        db=db, user_id=current_user.id, action=action,
                        resource_type=resource_type, resource_id=resource_id,
                        ip_address=ip,
                    )
                except Exception as e:
                    logger.error("Auto audit log failed: %s", e)
            
            return result
        return wrapper
    return decorator
