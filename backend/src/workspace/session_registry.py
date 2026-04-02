"""
SessionRegistry — persistent record of all OpenCode sessions for one workspace.

Stored at: {workspace}/logs/opencode_sessions.json
Append-only — sessions are never deleted, only status-updated.

Enables:
- Squid to reopen any past session
- Another Squid (Pattern A) to discover sessions from a peer's workspace
- The API to expose session history and cost
"""

import asyncio
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.workspace.opencode import OpenCodeLoopResult, OpenCodeSession


@dataclass
class SessionRecord:
    opencode_session_id: str   # OpenCode's stable SQLite ID
    created_at: str            # ISO timestamp
    topic: str                 # Human label (task description)
    hypothesis_id: str | None
    status: str                # "active" | "completed" | "failed" | "abandoned" | "output_limit_reached"
    turn_count: int
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    files_produced: list[str]
    last_response_summary: str  # Last OpenCode response, truncated to 200 chars


class SessionRegistry:
    """
    Persists OpenCode session history for one agent workspace.

    Uses a simple JSON file — no database, no external deps.
    All writes use read-modify-write with asyncio.to_thread to avoid
    blocking the event loop.
    """

    def __init__(self, workspace_path: Path) -> None:
        self._path = workspace_path / "logs" / "opencode_sessions.json"

    async def record_new(
        self,
        session: "OpenCodeSession",
        topic: str,
        hypothesis_id: str | None = None,
    ) -> None:
        """Record a newly created session."""
        record = SessionRecord(
            opencode_session_id=session.session_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            topic=topic,
            hypothesis_id=hypothesis_id,
            status="active",
            turn_count=0,
            total_input_tokens=0,
            total_output_tokens=0,
            total_cost_usd=0.0,
            files_produced=[],
            last_response_summary="",
        )
        await self._append(record)

    async def update(
        self,
        opencode_session_id: str,
        status: str,
        result: "OpenCodeLoopResult",
    ) -> None:
        """Update an existing session record with final results."""
        def _update() -> None:
            records = self._read_all()
            for r in records:
                if r["opencode_session_id"] == opencode_session_id:
                    r["status"] = status
                    r["turn_count"] = result.total_iterations
                    r["total_input_tokens"] = result.accumulated_usage.input_tokens
                    r["total_output_tokens"] = result.accumulated_usage.output_tokens
                    r["total_cost_usd"] = result.accumulated_usage.cost_usd
                    r["files_produced"] = result.files_produced
                    break
            self._write_all(records)

        await asyncio.to_thread(_update)

    async def list_all(self) -> list[SessionRecord]:
        """Return all session records, newest first."""
        def _list() -> list[SessionRecord]:
            return [SessionRecord(**r) for r in reversed(self._read_all())]

        return await asyncio.to_thread(_list)

    async def get(self, opencode_session_id: str) -> SessionRecord | None:
        """Return a specific session record by ID."""
        def _get() -> SessionRecord | None:
            for r in self._read_all():
                if r["opencode_session_id"] == opencode_session_id:
                    return SessionRecord(**r)
            return None

        return await asyncio.to_thread(_get)

    async def find_by_hypothesis(
        self, hypothesis_id: str
    ) -> list[SessionRecord]:
        """Return all sessions linked to a given hypothesis."""
        def _find() -> list[SessionRecord]:
            return [
                SessionRecord(**r)
                for r in self._read_all()
                if r.get("hypothesis_id") == hypothesis_id
            ]

        return await asyncio.to_thread(_find)

    # ── Internal helpers ──────────────────────────────────────────────

    def _read_all(self) -> list[dict]:
        if not self._path.exists():
            return []
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []

    def _write_all(self, records: list[dict]) -> None:
        self._path.write_text(
            json.dumps(records, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    async def _append(self, record: SessionRecord) -> None:
        def _do() -> None:
            records = self._read_all()
            records.append(asdict(record))
            self._write_all(records)

        await asyncio.to_thread(_do)
