"""
PostgreSQL async connection management via SQLAlchemy.

Provides an async engine and session factory. All database operations
go through this module to ensure consistent connection pooling and
lifecycle management.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import Settings, settings as default_settings


class PostgresConnection:
    """
    Manages an async SQLAlchemy engine and session factory.

    Usage:
        pg = PostgresConnection(settings)
        await pg.connect()
        async with pg.session() as session:
            result = await session.execute(text("SELECT 1"))
        await pg.close()
    """

    def __init__(self, config: Settings | None = None) -> None:
        self._config = config or default_settings
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

    async def connect(self) -> None:
        """Create the async engine and session factory."""
        self._engine = create_async_engine(
            self._config.database_url,
            echo=False,
            pool_size=10,
            max_overflow=20,
        )
        self._session_factory = async_sessionmaker(
            self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def close(self) -> None:
        """Dispose of the engine and release all connections."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_factory = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Yield an async SQLAlchemy session with automatic cleanup.

        Commits on success, rolls back on exception.
        """
        if not self._session_factory:
            raise RuntimeError(
                "Postgres engine not initialized — call connect() first."
            )
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    @property
    def engine(self) -> AsyncEngine:
        """Direct access to the engine for DDL operations."""
        if not self._engine:
            raise RuntimeError(
                "Postgres engine not initialized — call connect() first."
            )
        return self._engine
