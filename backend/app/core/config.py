from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "FINORA Digital Banking Platform"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    API_V1_PREFIX: str = "/api/v1"
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    SECRET_KEY: str = "CHANGE_ME_TO_A_SECURE_64_CHAR_RANDOM_HEX_STRING"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    DATABASE_URL: str = "postgresql+asyncpg://finora_user:finora_dev_pass@localhost:5432/finora_db"
    SQLITE_FALLBACK_URL: str = "sqlite+aiosqlite:///./finora_dev.db"
    USE_SQLITE_FALLBACK: bool = False

    REDIS_URL: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def active_database_url(self) -> str:
        if self.USE_SQLITE_FALLBACK:
            return self.SQLITE_FALLBACK_URL
        return self.DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    return Settings()