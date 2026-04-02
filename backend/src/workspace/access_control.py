"""
AccessControl — guards reads/writes to shared institutional data.

Advisory enforcement: WorkspaceManager calls assert_write() before
file operations. This is code-level, not OS-level — agents access
files only through WorkspaceManager, so this is sufficient.
"""

from pathlib import Path

from src.config import Settings


class AccessControl:
    """
    Enforces that agents can only write to their own workspace.

    Read access is allowed for:
    - The agent's own workspace (any path within workspace_root)
    - Shared read-only data directories (data/sources/, data/datasets/)

    Write access is allowed ONLY for the agent's own workspace.
    """

    def __init__(self, config: Settings, workspace_base: Path) -> None:
        self._workspace_base = workspace_base
        self._shared_data_roots = [
            Path(config.data_dir),
        ]

    def can_read(self, path: Path, agent_id: str, session_id: str) -> bool:
        """True if path is within the agent's workspace OR shared read-only data."""
        resolved = self._resolve(path)
        if self._in_workspace(resolved, agent_id, session_id):
            return True
        return any(
            str(resolved).startswith(str(root))
            for root in self._shared_data_roots
        )

    def can_write(self, path: Path, agent_id: str, session_id: str) -> bool:
        """True ONLY if path is within the agent's own workspace."""
        return self._in_workspace(self._resolve(path), agent_id, session_id)

    def assert_read(
        self, path: Path, agent_id: str, session_id: str
    ) -> None:
        """Raise PermissionError if the agent cannot read this path."""
        if not self.can_read(path, agent_id, session_id):
            raise PermissionError(
                f"Agent '{agent_id}' does not have read access to '{path}'. "
                f"Readable paths: own workspace or data/sources/."
            )

    def assert_write(
        self, path: Path, agent_id: str, session_id: str
    ) -> None:
        """Raise PermissionError if the agent cannot write to this path."""
        if not self.can_write(path, agent_id, session_id):
            raise PermissionError(
                f"Agent '{agent_id}' cannot write to '{path}'. "
                f"Write access is restricted to the agent's own workspace."
            )

    @property
    def shared_data_roots(self) -> list[Path]:
        return list(self._shared_data_roots)

    def _in_workspace(
        self, resolved: Path, agent_id: str, session_id: str
    ) -> bool:
        workspace_root = self._workspace_base / session_id / agent_id
        return str(resolved).startswith(str(workspace_root))

    @staticmethod
    def _resolve(path: Path) -> Path:
        try:
            return path.resolve()
        except OSError:
            return path.absolute()
