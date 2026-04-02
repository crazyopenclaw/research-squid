"""
Persistent UI/session projections stored in PostgreSQL.

This layer is intentionally thin. It stores API-facing session state and
translated UI events without changing the research engine or CLI flow.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from sqlalchemy import text

from src.db.connection import PostgresConnection


def _normalize_json(value: Any) -> Any:
    if value is None:
        return {}
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value


def _json_default(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, set):
        return list(value)
    if isinstance(value, tuple):
        return list(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except TypeError:
            pass
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


def _json_dumps(value: Any) -> str:
    return json.dumps(value, default=_json_default, ensure_ascii=False)


class ProjectionStore:
    """CRUD helpers for API-facing session projections and UI events."""

    def __init__(self, connection: PostgresConnection) -> None:
        self._conn = connection

    async def create_session(
        self,
        session_id: str,
        question: str,
        state: dict[str, Any],
        status: str = "starting",
    ) -> None:
        query = text(
            """
            INSERT INTO sessions (id, research_question, state, status, created_at, updated_at)
            VALUES (:id, :question, CAST(:state AS jsonb), :status, NOW(), NOW())
            ON CONFLICT (id) DO UPDATE SET
                research_question = EXCLUDED.research_question,
                state = EXCLUDED.state,
                status = EXCLUDED.status,
                updated_at = NOW()
            """
        )
        async with self._conn.session() as session:
            await session.execute(
                query,
                {
                    "id": session_id,
                    "question": question,
                    "state": _json_dumps(state),
                    "status": status,
                },
            )

    async def get_session(self, session_id: str) -> dict[str, Any] | None:
        query = text(
            """
            SELECT id, research_question, state, status, created_at, updated_at
            FROM sessions
            WHERE id = :id
            """
        )
        async with self._conn.session() as session:
            result = await session.execute(query, {"id": session_id})
            row = result.mappings().fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "question": row["research_question"],
            "state": _normalize_json(row["state"]),
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    async def upsert_session_state(
        self,
        session_id: str,
        question: str,
        state: dict[str, Any],
        status: str,
    ) -> None:
        query = text(
            """
            UPDATE sessions
            SET research_question = :question,
                state = CAST(:state AS jsonb),
                status = :status,
                updated_at = NOW()
            WHERE id = :id
            """
        )
        async with self._conn.session() as session:
            await session.execute(
                query,
                {
                    "id": session_id,
                    "question": question,
                    "state": _json_dumps(state),
                    "status": status,
                },
            )

    async def append_event(self, session_id: str, event: dict[str, Any]) -> None:
        query = text(
            """
            INSERT INTO event_log (session_id, event_type, agent_id, artifact_id, payload, created_at)
            VALUES (
                :session_id,
                :event_type,
                :agent_id,
                :artifact_id,
                CAST(:payload AS jsonb),
                NOW()
            )
            """
        )
        async with self._conn.session() as session:
            await session.execute(
                query,
                {
                    "session_id": session_id,
                    "event_type": event.get("kind", "event"),
                    "agent_id": event.get("agent_id") or None,
                    "artifact_id": (
                        event.get("refs", {}) or {}
                    ).get("artifact_id")
                    or None,
                    "payload": _json_dumps(event),
                },
            )

    async def list_events(
        self,
        session_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        query = text(
            """
            SELECT payload, created_at
            FROM event_log
            WHERE session_id = :session_id
            ORDER BY id DESC
            LIMIT :limit
            """
        )
        async with self._conn.session() as session:
            result = await session.execute(
                query,
                {"session_id": session_id, "limit": limit},
            )
            rows = result.mappings().fetchall()

        events: list[dict[str, Any]] = []
        for row in rows:
            payload = _normalize_json(row["payload"])
            if isinstance(payload, dict):
                if not payload.get("timestamp") and row.get("created_at"):
                    payload["timestamp"] = row["created_at"].isoformat()
                events.append(payload)
        return list(reversed(events))

    async def mark_nonterminal_sessions_interrupted(self) -> None:
        query = text(
            """
            SELECT id, research_question, state
            FROM sessions
            WHERE status IN ('starting', 'active', 'running', 'paused')
            """
        )
        async with self._conn.session() as session:
            result = await session.execute(query)
            rows = result.mappings().fetchall()

        for row in rows:
            state = _normalize_json(row["state"])
            snapshot = state.setdefault("snapshot", {})
            snapshot["status"] = "interrupted"
            state["error"] = "Session interrupted by backend restart."
            await self.upsert_session_state(
                session_id=row["id"],
                question=row["research_question"],
                state=state,
                status="interrupted",
            )
