from collections.abc import AsyncGenerator
from pathlib import Path
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from app.core.config import get_settings

settings = get_settings()

DB_FILE_PATH = Path(__file__).resolve().parents[2] / "finora_dev.db"
ACTIVE_URL = (
    f"sqlite+aiosqlite:///{DB_FILE_PATH.as_posix()}"
    if settings.USE_SQLITE_FALLBACK
    else settings.DATABASE_URL
)

engine_kwargs = {
    "echo": False,
    "future": True,
}

if not ACTIVE_URL.startswith("sqlite"):
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_async_engine(ACTIVE_URL, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_database_health() -> bool:
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        return False