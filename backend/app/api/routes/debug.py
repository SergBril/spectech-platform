"""Debug endpoints for testing monitoring."""

from fastapi import APIRouter

router = APIRouter(prefix="/debug")


@router.get("/test-log")
async def test_log():
    """Test structured logging."""
    import structlog

    logger = structlog.get_logger("spectech.debug")
    logger.info("TEST_LOG", message="Test log message", extra={"key": "value"})
    return {"status": "logged", "message": "Check server console"}


@router.get("/test-error")
async def test_error():
    """Test Sentry error tracking."""
    import structlog

    logger = structlog.get_logger("spectech.debug")
    logger.warning("TEST_ERROR", message="Test error for Sentry")
    raise ValueError("Test error for Sentry")
