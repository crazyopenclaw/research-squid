"""
WorkspaceManager — create, manage, and snapshot per-agent workspaces.

Each agent gets an isolated directory under:
  {workspace_base_path}/{session_id}/{agent_id}/

The manager enforces path isolation (no escaping the workspace root),
handles file I/O asynchronously via asyncio.to_thread, and maintains
a pool of long-lived OpenCodeServer processes (one per agent workspace).
"""

import asyncio
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from src.config import Settings

if TYPE_CHECKING:
    from src.workspace.opencode import OpenCodeServer
    from src.events.bus import EventBus


_MEMORY_TEMPLATE = """\
# Agent Memory: {agent_name}
Session: {session_id}
Subproblem: {subproblem}

---

<!-- APPEND-ONLY: Never delete entries. Add newest at bottom. -->

## {timestamp} — Iteration 0 (Initialized)
- Workspace created
- Assigned subproblem: {subproblem}
- Initial goals established
"""

_GOALS_TEMPLATE = """\
# Agent Goals: {agent_name}
Session: {session_id}

## Primary Subproblem
{subproblem}

## Current Goals
- [ ] investigate: Explore the subproblem and gather evidence
- [ ] hypothesize: Form testable hypotheses from evidence
- [ ] validate: Propose experiments to validate key hypotheses
"""

_HYPOTHESES_TEMPLATE = """\
# Agent Hypotheses: {agent_name}
Session: {session_id}

<!-- This file is a MIRROR of DAG hypotheses — rewritten each cycle, not append-only. -->
<!-- Historical state is preserved in Neo4j. -->

(No hypotheses yet — updated each research cycle)
"""

_NOTES_TEMPLATE = """\
# Agent Notes: {agent_name}
Session: {session_id}

<!-- Freeform running notes. Append-only. -->
"""


class WorkspaceManager:
    """
    Manages the filesystem layer for all agent workspaces.

    Responsibilities:
    - Create/delete/snapshot workspace directories
    - Enforce path isolation (prevent directory traversal)
    - Async file I/O (read/write/append) with memory.md protection
    - Pool of OpenCodeServer processes (one per agent workspace, lazy start)

    One WorkspaceManager is created per ResearchService instance and shared
    across all sessions. It is thread-safe at the directory level — each
    agent has its own directory so no cross-agent locking is needed.
    """

    def __init__(self, config: Settings, event_bus: "EventBus") -> None:
        self._config = config
        self._bus = event_bus
        self._base = Path(config.workspace_base_path)
        # Server pool: (agent_id, session_id) → OpenCodeServer
        self._servers: dict[tuple[str, str], "OpenCodeServer"] = {}

    async def initialize(self) -> None:
        """Create the base workspace directory if it doesn't exist."""
        await asyncio.to_thread(self._base.mkdir, parents=True, exist_ok=True)

    # ── Lifecycle ──────────────────────────────────────────────────────

    async def create_workspace(
        self,
        agent_id: str,
        session_id: str,
        agent_name: str,
        subproblem: str,
    ) -> Path:
        """
        Create the workspace directory tree for one agent.

        Idempotent — if the directory already exists, returns its path
        without reinitializing files (prevents overwriting in-progress work).
        """
        root = self.workspace_root(agent_id, session_id)

        def _create() -> None:
            if root.exists():
                return  # already created — idempotent
            root.mkdir(parents=True, exist_ok=True)

            # Create subdirectories
            for subdir in ("scripts", "data", "outputs", "logs", "scratch"):
                (root / subdir).mkdir(exist_ok=True)

            # Seed files
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            (root / "memory.md").write_text(
                _MEMORY_TEMPLATE.format(
                    agent_name=agent_name,
                    session_id=session_id,
                    subproblem=subproblem,
                    timestamp=ts,
                ),
                encoding="utf-8",
            )
            (root / "goals.md").write_text(
                _GOALS_TEMPLATE.format(
                    agent_name=agent_name,
                    session_id=session_id,
                    subproblem=subproblem,
                ),
                encoding="utf-8",
            )
            (root / "hypotheses.md").write_text(
                _HYPOTHESES_TEMPLATE.format(
                    agent_name=agent_name,
                    session_id=session_id,
                ),
                encoding="utf-8",
            )
            (root / "notes.md").write_text(
                _NOTES_TEMPLATE.format(
                    agent_name=agent_name,
                    session_id=session_id,
                ),
                encoding="utf-8",
            )
            (root / "beliefs.json").write_text("[]", encoding="utf-8")
            (root / "logs" / "opencode_sessions.json").write_text(
                "[]", encoding="utf-8"
            )
            (root / "logs" / "opencode_conversation.md").write_text(
                "", encoding="utf-8"
            )

        await asyncio.to_thread(_create)
        return root

    async def delete_workspace(self, agent_id: str, session_id: str) -> None:
        """Delete an agent's workspace directory and all its contents."""
        import shutil
        root = self.workspace_root(agent_id, session_id)
        if await asyncio.to_thread(root.exists):
            await asyncio.to_thread(shutil.rmtree, root)

    async def snapshot_workspace(self, agent_id: str, session_id: str) -> Path:
        """
        Zip the entire workspace into {base}/{session_id}/{agent_id}.zip.

        Returns the path to the zip file. Non-fatal if workspace doesn't exist.
        """
        root = self.workspace_root(agent_id, session_id)
        zip_path = self._base / session_id / f"{agent_id}.zip"

        def _zip() -> None:
            if not root.exists():
                return
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file in root.rglob("*"):
                    if file.is_file():
                        zf.write(file, file.relative_to(root))

        await asyncio.to_thread(_zip)
        return zip_path

    async def snapshot_session(self, session_id: str) -> None:
        """
        Snapshot all agent workspaces for a session.

        Called at session end before stopping servers. Non-fatal if any
        individual workspace snapshot fails.
        """
        session_dir = self._base / session_id
        if not await asyncio.to_thread(session_dir.exists):
            return
        agent_ids = await asyncio.to_thread(
            lambda: [d.name for d in session_dir.iterdir() if d.is_dir()]
        )
        from src.models.events import Event, EventType
        for agent_id in agent_ids:
            try:
                await self.snapshot_workspace(agent_id, session_id)
                await self._bus.publish(Event(
                    event_type=EventType.WORKSPACE_SNAPSHOTTED,
                    agent_id=agent_id,
                    session_id=session_id,
                ))
            except Exception:
                pass  # Non-fatal

    async def cleanup_session(self, session_id: str) -> None:
        """
        Delete all agent workspaces for a session.

        Only called when workspace_keep_after_session=False.
        """
        import shutil
        session_dir = self._base / session_id
        if await asyncio.to_thread(session_dir.exists):
            await asyncio.to_thread(shutil.rmtree, session_dir)

    # ── File I/O ──────────────────────────────────────────────────────

    async def read_file(
        self, agent_id: str, session_id: str, relative_path: str
    ) -> str:
        path = self._safe_path(agent_id, session_id, relative_path)
        return await asyncio.to_thread(path.read_text, encoding="utf-8")

    async def write_file(
        self,
        agent_id: str,
        session_id: str,
        relative_path: str,
        content: str,
    ) -> None:
        """
        Write content to a workspace file.

        Raises PermissionError if relative_path == "memory.md" —
        memory is append-only, use append_file() instead.
        """
        if relative_path == "memory.md":
            raise PermissionError(
                "memory.md is append-only. Use append_file() to add entries."
            )
        path = self._safe_path(agent_id, session_id, relative_path)
        # Enforce max file size
        max_bytes = self._config.workspace_max_file_size_kb * 1024
        if len(content.encode("utf-8")) > max_bytes:
            raise ValueError(
                f"Content exceeds workspace_max_file_size_kb "
                f"({self._config.workspace_max_file_size_kb} KB)"
            )
        await asyncio.to_thread(
            path.write_text, content, encoding="utf-8"
        )

    async def append_file(
        self,
        agent_id: str,
        session_id: str,
        relative_path: str,
        content: str,
    ) -> None:
        """Append content to a workspace file (creates it if missing)."""
        path = self._safe_path(agent_id, session_id, relative_path)

        def _append() -> None:
            with path.open("a", encoding="utf-8") as f:
                f.write(content)

        await asyncio.to_thread(_append)

    async def list_files(self, agent_id: str, session_id: str) -> list[str]:
        """List all files in the workspace (excluding .history/)."""
        root = self.workspace_root(agent_id, session_id)

        def _list() -> list[str]:
            if not root.exists():
                return []
            return [
                str(p.relative_to(root))
                for p in root.rglob("*")
                if p.is_file() and ".history" not in p.parts
            ]

        return await asyncio.to_thread(_list)

    # ── OpenCode Server Pool ──────────────────────────────────────────

    async def get_or_start_server(
        self, agent_id: str, session_id: str
    ) -> "OpenCodeServer":
        """
        Return the cached OpenCodeServer for this workspace, starting it if needed.

        The server stays alive across all Squid cycles until stop_all_servers().
        """
        key = (agent_id, session_id)
        server = self._servers.get(key)

        if server is None or not server.is_running:
            from src.workspace.opencode import OpenCodeServer
            root = self.workspace_root(agent_id, session_id)
            server = OpenCodeServer(
                workspace_path=root,
                config=self._config,
                event_bus=self._bus,
            )
            await server.start()
            self._servers[key] = server

        return server

    async def stop_all_servers(self, session_id: str) -> None:
        """Stop all OpenCode servers for a given session."""
        keys_to_remove = [
            key for key in self._servers if key[1] == session_id
        ]
        for key in keys_to_remove:
            server = self._servers.pop(key)
            try:
                await server.stop()
            except Exception:
                pass  # Non-fatal — server may have already exited

    # ── Path Helpers ──────────────────────────────────────────────────

    def workspace_root(self, agent_id: str, session_id: str) -> Path:
        """Return the absolute root path for an agent's workspace."""
        return self._base / session_id / agent_id

    def _safe_path(
        self, agent_id: str, session_id: str, relative_path: str
    ) -> Path:
        """
        Resolve a relative path within the workspace.

        CRITICAL: Resolves symlinks and verifies the result stays inside
        the workspace root. Raises PermissionError on path traversal attempts.
        Also ensures parent directories exist.
        """
        root = self.workspace_root(agent_id, session_id)
        # Join without resolving first (path may not exist yet)
        candidate = root / relative_path
        # Resolve to catch `../` traversal
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate.absolute()

        root_resolved = root.resolve() if root.exists() else root.absolute()

        if not str(resolved).startswith(str(root_resolved)):
            raise PermissionError(
                f"Path '{relative_path}' escapes workspace root. "
                "Directory traversal is not allowed."
            )

        # Ensure parent directory exists
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved
