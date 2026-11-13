from datetime import datetime, timezone
from fastapi import APIRouter
from app.core.config import get_settings
from app.db.session import check_database_health

router = APIRouter(tags=["System Health"])
settings = get_settings()


@router.get("/health")
async def health_check() -> dict:
    db_ok = await check_database_health()
    return {
        "status": "healthy" if db_ok else "degraded",
        "platform": "FINORA",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database_connected": db_ok,
        "database_engine": "sqlite" if settings.USE_SQLITE_FALLBACK else "postgresql",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }