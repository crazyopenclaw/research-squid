"""
Neo4j driver management.

Provides an async-compatible Neo4j driver as a context manager.
The driver is created once and reused across the application lifetime.
All graph operations go through this connection.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession, NotificationDisabledCategory

from src.config import Settings, settings as default_settings


class Neo4jConnection:
    """
    Manages a Neo4j async driver lifecycle.

    Usage:
        conn = Neo4jConnection(settings)
        await conn.connect()
        async with conn.session() as session:
            result = await session.run("MATCH (n) RETURN n LIMIT 1")
        await conn.close()
    """

    def __init__(self, config: Settings | None = None) -> None:
        self._config = config or default_settings
        self._driver: AsyncDriver | None = None

    async def connect(self) -> None:
        """Establish connection to Neo4j."""
        self._driver = AsyncGraphDatabase.driver(
            self._config.neo4j_uri,
            auth=(self._config.neo4j_user, self._config.neo4j_password),
            notifications_disabled_categories=[NotificationDisabledCategory.UNRECOGNIZED],
        )
        # Verify connectivity
        await self._driver.verify_connectivity()

    async def close(self) -> None:
        """Close the Neo4j driver and release resources."""
        if self._driver:
            await self._driver.close()
            self._driver = None

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Yield an async Neo4j session.

        Raises RuntimeError if connect() hasn't been called.
        """
        if not self._driver:
            raise RuntimeError(
                "Neo4j driver not initialized — call connect() first."
            )
        session = self._driver.session()
        try:
            yield session
        finally:
            await session.close()

    @property
    def driver(self) -> AsyncDriver:
        """Direct access to the driver for advanced use cases."""
        if not self._driver:
            raise RuntimeError(
                "Neo4j driver not initialized — call connect() first."
            )
        return self._driver
