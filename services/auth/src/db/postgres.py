from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

from core.settings import settings


class Base(DeclarativeBase):
    """Базовый класс для ORM-моделей."""


DATABASE_URL = (
    f"postgresql+asyncpg://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)

engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True,
    poolclass=NullPool,
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)

# Fixed advisory lock ids for auth startup/bootstrap.
_STARTUP_LOCK_KEY_1 = 41001
_STARTUP_LOCK_KEY_2 = 1


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


@asynccontextmanager
async def startup_lock():
    """Serialize auth startup init across multiple workers/processes."""
    params = {"key1": _STARTUP_LOCK_KEY_1, "key2": _STARTUP_LOCK_KEY_2}
    async with engine.connect() as conn:
        await conn.execute(
            text("SELECT pg_advisory_lock(:key1, :key2)"),
            params,
        )
        try:
            yield
        finally:
            await conn.execute(
                text("SELECT pg_advisory_unlock(:key1, :key2)"),
                params,
            )


async def init_models(*, reset: bool = False) -> None:
    """Создание таблиц.

    Для production лучше использовать Alembic migrations.
    """
    from infrastructure.postgres import models  # noqa: F401

    async with engine.begin() as conn:
        if reset:
            await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
