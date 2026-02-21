from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


# ── Async (FastAPI) ──────────────────────────────────────────────────────────
async_engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False,
)
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Sync (Celery workers) ────────────────────────────────────────────────────
sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    pool_pre_ping=True,
    echo=False,
)
SyncSessionLocal = sessionmaker(
    sync_engine,
    class_=Session,
    expire_on_commit=False,
)


# ── Base для SQLAlchemy-моделей ──────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Dependency для FastAPI ───────────────────────────────────────────────────
async def get_async_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
