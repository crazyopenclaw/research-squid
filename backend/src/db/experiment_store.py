"""
Experiment tracking in PostgreSQL.

Provides CRUD operations for experiment lifecycle management.
Complements Neo4j storage — Postgres handles the operational
tracking (status, timing, container IDs) while Neo4j stores
the graph relationships.
"""

from typing import Any

from sqlalchemy import text

from src.db.connection import PostgresConnection


class ExperimentStore:
    """
    CRUD operations for experiment tracking in PostgreSQL.

    Usage:
        store = ExperimentStore(pg_connection)
        await store.create(experiment_id, hypothesis_id, spec, agent_id)
        await store.update_status(experiment_id, "completed", exit_code=0)
    """

    def __init__(self, connection: PostgresConnection) -> None:
        self._conn = connection

    async def create(
        self,
        experiment_id: str,
        hypothesis_id: str,
        spec: dict[str, Any],
        created_by: str,
    ) -> None:
        """Record a new experiment in the tracking table."""
        query = text("""
            INSERT INTO experiments (id, hypothesis_id, spec, created_by)
            VALUES (:id, :hypothesis_id, CAST(:spec AS jsonb), :created_by)
            ON CONFLICT (id) DO NOTHING
        """)
        async with self._conn.session() as session:
            await session.execute(query, {
                "id": experiment_id,
                "hypothesis_id": hypothesis_id,
                "spec": str(spec),
                "created_by": created_by,
            })

    async def update_status(
        self,
        experiment_id: str,
        status: str,
        exit_code: int | None = None,
        stdout: str = "",
        stderr: str = "",
        execution_time: float | None = None,
        container_id: str = "",
    ) -> None:
        """Update an experiment's execution status and results."""
        query = text("""
            UPDATE experiments
            SET status = :status,
                exit_code = :exit_code,
                stdout = :stdout,
                stderr = :stderr,
                execution_time_seconds = :execution_time,
                container_id = :container_id,
                completed_at = CASE WHEN :status IN ('completed', 'failed') THEN NOW() ELSE completed_at END,
                started_at = CASE WHEN :status = 'running' THEN NOW() ELSE started_at END
            WHERE id = :id
        """)
        async with self._conn.session() as session:
            await session.execute(query, {
                "id": experiment_id,
                "status": status,
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "execution_time": execution_time,
                "container_id": container_id,
            })

    async def get(self, experiment_id: str) -> dict[str, Any] | None:
        """Fetch a single experiment by ID."""
        query = text("SELECT * FROM experiments WHERE id = :id")
        async with self._conn.session() as session:
            result = await session.execute(query, {"id": experiment_id})
            row = result.mappings().fetchone()
            return dict(row) if row else None

    async def get_by_status(
        self, status: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Fetch experiments by status."""
        query = text(
            "SELECT * FROM experiments WHERE status = :status "
            "ORDER BY created_at DESC LIMIT :limit"
        )
        async with self._conn.session() as session:
            result = await session.execute(
                query, {"status": status, "limit": limit}
            )
            return [dict(row) for row in result.mappings()]
