"""Shared async DB plumbing for Celery tasks.

Each Celery task runs its own ``asyncio.run`` (fresh event loop). Reusing a
single module-level engine across loops breaks asyncpg ("Future attached to a
different loop"), so an engine is created per task — but it MUST be disposed
before the loop closes, otherwise the connection pool leaks until Postgres runs
out of clients. These context managers create and dispose the engine within the
same loop.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config.settings import get_settings


@asynccontextmanager
async def worker_engine() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Yield a sessionmaker bound to a per-task engine, disposed on exit.

    Use when a task needs multiple concurrent sessions (e.g. fan-out via
    ``asyncio.gather``) — each ``AsyncSession`` is single-use/non-concurrent, so
    parallel work needs one session each, all sharing this engine's pool.
    """
    engine = create_async_engine(get_settings().database_url, echo=False)
    try:
        yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    finally:
        await engine.dispose()


@asynccontextmanager
async def worker_session() -> AsyncIterator[AsyncSession]:
    """Yield a single session bound to a per-task engine, disposed on exit."""
    async with worker_engine() as factory, factory() as session:
        yield session
