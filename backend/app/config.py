from pydantic_settings import BaseSettings
from functools import lru_cache
import os


def _fix_async_url(url: str) -> str:
    """Convert postgresql:// to postgresql+asyncpg:// for async engine."""
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def _fix_sync_url(url: str) -> str:
    """Ensure sync URL uses plain postgresql:// driver."""
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


class Settings(BaseSettings):
    # Database — Railway injects DATABASE_URL as postgresql://...
    database_url: str = "postgresql+asyncpg://docflow:docflow_secret@localhost:5432/docflow_db"
    sync_database_url: str = "postgresql://docflow:docflow_secret@localhost:5432/docflow_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Upload
    upload_dir: str = "./uploads"
    max_upload_size: int = 50 * 1024 * 1024  # 50MB

    # App
    app_name: str = "DocFlow"
    debug: bool = False

    def model_post_init(self, __context):
        # Auto-fix database URL formats
        object.__setattr__(self, "database_url", _fix_async_url(self.database_url))
        object.__setattr__(self, "sync_database_url", _fix_sync_url(self.sync_database_url))

        # If only DATABASE_URL is set (Railway), derive sync URL from it
        raw = os.environ.get("DATABASE_URL", "")
        if raw and not os.environ.get("SYNC_DATABASE_URL"):
            object.__setattr__(self, "sync_database_url", _fix_sync_url(raw))

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()
