"""
MemoryEnforcer — validates and maintains memory.md in agent workspaces.

Ensures agents actually update their memory each cycle and that the
file doesn't grow unboundedly (archives older entries when needed).
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.workspace.manager import WorkspaceManager
    from src.config import Settings

# Matches memory entry headers like: ## 2026-04-05 14:30
_ENTRY_HEADER_RE = re.compile(r"^## \d{4}-\d{2}-\d{2} \d{2}:\d{2}", re.MULTILINE)


@dataclass
class MemoryValidationResult:
    is_valid: bool
    entry_count: int
    last_updated: datetime | None
    issues: list[str]


class MemoryEnforcer:
    """
    Validates memory.md and enforces update discipline.

    Called at the end of each Squid cycle to ensure agents are
    recording meaningful findings. If no update was made, writes a
    minimal entry automatically (soft enforcement — never fails a cycle).

    Also prunes memory.md when it exceeds workspace_memory_max_entries
    by archiving the oldest 50% to memory.archive.md.
    """

    def __init__(
        self,
        workspace_manager: "WorkspaceManager",
        config: "Settings",
    ) -> None:
        self._manager = workspace_manager
        self._config = config

    async def validate_memory_update(
        self,
        agent_id: str,
        session_id: str,
    ) -> MemoryValidationResult:
        """
        Check whether memory.md has been updated with a valid entry today.
        """
        try:
            content = await self._manager.read_file(
                agent_id, session_id, "memory.md"
            )
        except FileNotFoundError:
            return MemoryValidationResult(
                is_valid=False,
                entry_count=0,
                last_updated=None,
                issues=["memory.md does not exist"],
            )

        headers = _ENTRY_HEADER_RE.findall(content)
        entry_count = len(headers)
        issues: list[str] = []

        last_updated: datetime | None = None
        if headers:
            try:
                ts_str = headers[-1].lstrip("## ").strip()
                last_updated = datetime.strptime(
                    ts_str, "%Y-%m-%d %H:%M"
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                pass

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        has_today_entry = any(h for h in headers if today in h)

        if not has_today_entry:
            issues.append(f"No entry for today ({today}) found in memory.md")

        # Check that the last entry has some content after the header
        if headers:
            last_header = headers[-1]
            after_header = content.split(last_header, 1)[-1].strip()
            lines_after = [
                ln for ln in after_header.split("\n")
                if ln.strip() and not ln.startswith("##")
            ]
            if not lines_after or all(
                len(ln.strip()) < self._config.workspace_memory_min_entry_length
                for ln in lines_after
            ):
                issues.append("Last memory entry is empty or too short")

        return MemoryValidationResult(
            is_valid=len(issues) == 0,
            entry_count=entry_count,
            last_updated=last_updated,
            issues=issues,
        )

    async def enforce_memory_update(
        self,
        agent_id: str,
        session_id: str,
        iteration: int,
        findings: str,
    ) -> None:
        """
        Ensure memory.md has an entry for this cycle.

        If the agent didn't write one, appends a minimal auto-generated
        entry and emits a warning event. Never raises — enforcement is soft.
        """
        validation = await self.validate_memory_update(agent_id, session_id)

        if not validation.is_valid:
            # Auto-write a minimal entry
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
            auto_entry = (
                f"\n## {ts} — Iteration {iteration} (auto-logged)\n"
                f"- {findings[:200] if findings else 'No significant findings this cycle'}\n"
            )
            await self._manager.append_file(
                agent_id, session_id, "memory.md", auto_entry
            )

            from src.models.events import Event, EventType
            await self._manager._bus.publish(Event(
                event_type=EventType.WORKSPACE_MEMORY_UPDATED,
                agent_id=agent_id,
                session_id=session_id,
                payload={
                    "auto_logged": True,
                    "issues": validation.issues,
                    "iteration": iteration,
                },
            ))

    async def prune_if_needed(
        self,
        agent_id: str,
        session_id: str,
    ) -> None:
        """
        Archive oldest entries when memory.md exceeds max_entries.

        Archives the oldest 50% of entries to memory.archive.md,
        replacing them with a single summary line in memory.md.
        Pure string manipulation — no LLM call.
        """
        try:
            content = await self._manager.read_file(
                agent_id, session_id, "memory.md"
            )
        except FileNotFoundError:
            return

        headers = list(_ENTRY_HEADER_RE.finditer(content))
        if len(headers) <= self._config.workspace_memory_max_entries:
            return  # No pruning needed

        # Split at the halfway point
        cutoff_idx = len(headers) // 2
        cutoff_match = headers[cutoff_idx]
        archive_section = content[: cutoff_match.start()]
        keep_section = content[cutoff_match.start():]

        # Determine date range of archived entries
        first_header = headers[0].group().lstrip("## ").strip()
        last_archived_header = headers[cutoff_idx - 1].group().lstrip("## ").strip()
        archive_summary = (
            f"\n## ARCHIVED — {first_header} → {last_archived_header} "
            f"({cutoff_idx} entries, see memory.archive.md)\n"
        )

        # Preserve header section (lines before first entry)
        header_end = headers[0].start() if headers else len(content)
        preamble = content[:header_end]
        new_content = preamble + archive_summary + keep_section

        # Append to archive file
        await self._manager.append_file(
            agent_id, session_id, "memory.archive.md", archive_section
        )
        # Rewrite memory.md through WorkspaceManager (enforces size limits)
        await self._manager.rewrite_file(
            agent_id, session_id, "memory.md", new_content
        )
