"""
FileTracker — simple per-file version history for workspace files.

Snapshots are stored in {workspace_root}/.history/{filename}.{timestamp}
so they don't pollute the agent's view of its own workspace.

Does NOT use git — simple file copies are sufficient and have no
external dependencies.
"""

import asyncio
import difflib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class FileVersion:
    timestamp: datetime
    path: Path       # path to the historical snapshot
    size_bytes: int


class FileTracker:
    """
    Per-file version history stored in {workspace_root}/.history/.

    Called by WorkspaceManager on every write_file() to preserve
    a snapshot before overwriting.
    """

    def __init__(self, workspace_root: Path) -> None:
        self._root = workspace_root
        self._history_dir = workspace_root / ".history"

    async def track_write(self, file_path: Path, content: str) -> None:
        """
        Save a snapshot of file_path before its content is overwritten.

        The snapshot is written to .history/{relative_name}.{iso_timestamp}
        """
        def _snapshot() -> None:
            self._history_dir.mkdir(exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            rel = file_path.relative_to(self._root)
            # Flatten path separators for safe filename
            flat_name = str(rel).replace("/", "_").replace("\\", "_")
            snapshot_path = self._history_dir / f"{flat_name}.{ts}"
            snapshot_path.write_text(content, encoding="utf-8")

        await asyncio.to_thread(_snapshot)

    async def get_history(self, file_path: Path) -> list[FileVersion]:
        """Return all historical snapshots for a file, oldest first."""
        def _list() -> list[FileVersion]:
            if not self._history_dir.exists():
                return []
            rel = file_path.relative_to(self._root)
            flat_name = str(rel).replace("/", "_").replace("\\", "_")
            versions = []
            for p in self._history_dir.iterdir():
                if p.name.startswith(flat_name + ".") and p.is_file():
                    # Parse timestamp from suffix
                    ts_str = p.name[len(flat_name) + 1:]
                    try:
                        ts = datetime.strptime(ts_str, "%Y%m%dT%H%M%S%f").replace(
                            tzinfo=timezone.utc
                        )
                    except ValueError:
                        ts = datetime.now(timezone.utc)
                    versions.append(
                        FileVersion(
                            timestamp=ts,
                            path=p,
                            size_bytes=p.stat().st_size,
                        )
                    )
            return sorted(versions, key=lambda v: v.timestamp)

        return await asyncio.to_thread(_list)

    async def diff(self, file_path: Path, v1: str, v2: str) -> str:
        """
        Return a unified diff between two snapshot timestamps (ISO strings).

        v1 and v2 are timestamp strings matching the snapshot filename suffix.
        Returns empty string if either version is not found.
        """
        def _diff() -> str:
            rel = file_path.relative_to(self._root)
            flat_name = str(rel).replace("/", "_").replace("\\", "_")

            def read_version(ts: str) -> list[str]:
                p = self._history_dir / f"{flat_name}.{ts}"
                if p.exists():
                    return p.read_text(encoding="utf-8").splitlines(keepends=True)
                return []

            lines_v1 = read_version(v1)
            lines_v2 = read_version(v2)
            return "".join(
                difflib.unified_diff(lines_v1, lines_v2, fromfile=v1, tofile=v2)
            )

        return await asyncio.to_thread(_diff)
