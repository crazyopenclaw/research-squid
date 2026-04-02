"""
WorkspaceTools — the only interface SquidAgent uses to interact with its workspace.

All workspace operations go through this class, which delegates to the
appropriate component (WorkspaceManager, OpenCodeServer, SessionRegistry, etc.).

Instantiated once per Squid run() invocation via ResearchCycleBuilder._run_squid().
The underlying WorkspaceManager and OpenCodeServer are long-lived (shared across
all runs for the same agent workspace).
"""

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.workspace.manager import WorkspaceManager
    from src.workspace.opencode import OpenCodeServer, OpenCodeLoopResult, TokenUsage
    from src.workspace.submitter import ExperimentSubmitter
    from src.workspace.memory_enforcer import MemoryEnforcer
    from src.events.bus import EventBus
    from src.models.experiment import ExperimentSpec


# ── OpenCodeTask model ─────────────────────────────────────────────────────

from pydantic import BaseModel


class OpenCodeTask(BaseModel):
    """
    Structured task for OpenCode to execute, produced by the Squid's LLM.

    The Squid's structured output call produces this as an optional field.
    Only set when the Squid decides code exploration would advance a hypothesis.
    """
    hypothesis_id: str
    topic: str               # Short label; also used as the OpenCode session title
    initial_prompt: str      # First message sent to OpenCode
    success_criterion: str   # What the Squid checks to decide if output is sufficient
    expected_output_file: str  # Relative workspace path where output should appear
    review_guidance: str     # What to tell OpenCode if the first turn isn't satisfying
    max_iterations: int = 3  # Max Squid→OpenCode review rounds


# ── Result types ──────────────────────────────────────────────────────────

@dataclass
class ReviewResult:
    satisfied: bool
    reason: str
    followup_instruction: str


@dataclass
class OpenCodeLoopResult:
    opencode_session_id: str
    topic: str
    satisfied: bool
    status: str   # "completed" | "failed" | "abandoned" | "output_limit_reached"
    total_iterations: int
    files_produced: list[str]
    accumulated_usage: "TokenUsage"


# ── Review logic ──────────────────────────────────────────────────────────

def _review_output(
    task: OpenCodeTask,
    turn: Any,  # OpenCodeTurnResult
    output_content: str,
) -> ReviewResult:
    """
    Determine if OpenCode's turn satisfied the task.

    Deliberately simple — no LLM call.
    Checks: (1) did OpenCode write any files? (2) does the expected output file
    exist with content? The Squid reasons about quality in the next cycle.
    """
    if not turn.files_modified:
        return ReviewResult(
            satisfied=False,
            reason="No files were created or modified.",
            followup_instruction=(
                f"The previous turn produced no file output.\n"
                f"Please write the result to `{task.expected_output_file}`.\n\n"
                f"{task.review_guidance}"
            ),
        )

    if task.expected_output_file and not output_content.strip():
        return ReviewResult(
            satisfied=False,
            reason=f"Expected output file `{task.expected_output_file}` is missing or empty.",
            followup_instruction=(
                f"The file `{task.expected_output_file}` does not exist or is empty.\n\n"
                f"{task.review_guidance}"
            ),
        )

    return ReviewResult(
        satisfied=True,
        reason="Output file exists with content.",
        followup_instruction="",
    )


# ── WorkspaceTools ────────────────────────────────────────────────────────

class WorkspaceTools:
    """
    High-level workspace operations for SquidAgent.

    This is the ONLY interface squids should use to interact with their workspace.
    """

    def __init__(
        self,
        agent_id: str,
        session_id: str,
        workspace_manager: "WorkspaceManager",
        opencode_server: "OpenCodeServer",
        submitter: "ExperimentSubmitter",
        enforcer: "MemoryEnforcer",
        event_bus: "EventBus",
    ) -> None:
        self._agent_id = agent_id
        self._session_id = session_id
        self._manager = workspace_manager
        self._server = opencode_server
        self._submitter = submitter
        self._enforcer = enforcer
        self._bus = event_bus

        from src.workspace.session_registry import SessionRegistry
        self._registry = SessionRegistry(
            workspace_manager.workspace_root(agent_id, session_id)
        )
        self._opencode_tasks_used = 0

    # ── Memory ────────────────────────────────────────────────────────

    async def append_memory(self, content: str, iteration: int) -> None:
        """Format content with timestamp and append to memory.md."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        entry = f"\n## {ts} — Iteration {iteration}\n{content}\n"
        await self._manager.append_file(
            self._agent_id, self._session_id, "memory.md", entry
        )
        from src.models.events import Event, EventType
        await self._bus.publish(Event(
            event_type=EventType.WORKSPACE_MEMORY_UPDATED,
            agent_id=self._agent_id,
            session_id=self._session_id,
            payload={"iteration": iteration},
        ))

    # ── Goals ─────────────────────────────────────────────────────────

    async def read_goals(self) -> str:
        """Return the content of goals.md."""
        try:
            return await self._manager.read_file(
                self._agent_id, self._session_id, "goals.md"
            )
        except FileNotFoundError:
            return ""

    async def update_goals(self, updates: dict[str, str]) -> None:
        """
        Update goal statuses in goals.md.

        updates = {"goal_text": "completed" | "in_progress" | "blocked"}
        Replaces "- [ ] goal_text" with "- [x] goal_text" etc.
        """
        try:
            content = await self._manager.read_file(
                self._agent_id, self._session_id, "goals.md"
            )
        except FileNotFoundError:
            return

        for goal_text, status in updates.items():
            marker = {"completed": "[x]", "in_progress": "[~]", "blocked": "[!]"}.get(
                status, "[ ]"
            )
            # Replace any existing marker for this goal
            import re
            content = re.sub(
                rf"- \[.\] {re.escape(goal_text)}",
                f"- {marker} {goal_text}",
                content,
            )

        await self._manager.write_file(
            self._agent_id, self._session_id, "goals.md", content
        )

    # ── Hypotheses ────────────────────────────────────────────────────

    async def sync_hypotheses_from_dag(
        self, hypotheses: list[dict[str, Any]]
    ) -> None:
        """
        Rewrite hypotheses.md from the agent's current DAG hypotheses.

        This file is a MIRROR (not append-only) — rewritten each cycle.
        Historical state is preserved in Neo4j.
        """
        lines = [
            "# Agent Hypotheses\n",
            f"Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}\n\n",
        ]
        for h in hypotheses:
            confidence = h.get("confidence", 0.0)
            status = h.get("adjudication_status", "pending")
            text = h.get("statement", h.get("text", str(h)))
            lines.append(f"- [{status}] (conf={confidence:.2f}) {text}\n")

        await self._manager.write_file(
            self._agent_id,
            self._session_id,
            "hypotheses.md",
            "".join(lines),
        )

    # ── Beliefs ───────────────────────────────────────────────────────

    async def update_beliefs(self, hypotheses: list[dict[str, Any]]) -> None:
        """
        Rewrite beliefs.json from hypothesis confidence values.

        beliefs.json is auto-populated — not hand-crafted by the agent.
        """
        beliefs = [
            {
                "hypothesis_id": h.get("id", ""),
                "statement": h.get("statement", h.get("text", "")),
                "confidence": h.get("confidence", 0.0),
                "status": h.get("adjudication_status", "pending"),
            }
            for h in hypotheses
        ]
        await self._manager.write_file(
            self._agent_id,
            self._session_id,
            "beliefs.json",
            json.dumps(beliefs, indent=2, ensure_ascii=False),
        )

    # ── Notes ─────────────────────────────────────────────────────────

    async def append_notes(self, content: str) -> None:
        """Append freeform notes to notes.md."""
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        entry = f"\n### {ts}\n{content}\n"
        await self._manager.append_file(
            self._agent_id, self._session_id, "notes.md", entry
        )

    async def read_notes(self) -> str:
        """Return the content of notes.md."""
        try:
            return await self._manager.read_file(
                self._agent_id, self._session_id, "notes.md"
            )
        except FileNotFoundError:
            return ""

    # ── OpenCode Budget ───────────────────────────────────────────────

    def opencode_tasks_remaining(self) -> int:
        """How many more OpenCode tasks this agent can run this session."""
        return max(
            0,
            self._manager._config.workspace_max_opencode_tasks_per_session
            - self._opencode_tasks_used,
        )

    # ── OpenCode Loop ─────────────────────────────────────────────────

    async def run_opencode_loop(
        self, task: OpenCodeTask
    ) -> "OpenCodeLoopResult | None":
        """
        Iterative Squid → OpenCode loop.

        Squid reviews each turn; if not satisfied, sends a corrective
        follow-up. Continues until satisfied or max_iterations reached.

        Returns None if OpenCode is unavailable or quota is exhausted.
        """
        from src.models.events import Event, EventType

        if not shutil.which("opencode"):
            await self._bus.publish(Event(
                event_type=EventType.WORKSPACE_OPENCODE_UNAVAILABLE,
                payload={"agent_id": self._agent_id},
            ))
            return None

        max_tasks = self._manager._config.workspace_max_opencode_tasks_per_session
        if self._opencode_tasks_used >= max_tasks:
            await self._bus.publish(Event(
                event_type=EventType.WORKSPACE_OPENCODE_UNAVAILABLE,
                payload={
                    "agent_id": self._agent_id,
                    "reason": f"quota exhausted ({max_tasks} tasks)",
                },
            ))
            return None

        self._opencode_tasks_used += 1

        session = await self._server.new_session(title=task.topic)
        await self._registry.record_new(
            session, topic=task.topic, hypothesis_id=task.hypothesis_id
        )

        current_prompt = task.initial_prompt
        conversation_log = [f"# OpenCode Session: {task.topic}\n\n"]
        files_produced: set[str] = set()
        satisfied = False
        total_iterations = 0
        status = "abandoned"

        try:
            max_iters = max(1, task.max_iterations)
            for i in range(max_iters):
                total_iterations = i + 1
                turn = await session.send(current_prompt)
                files_produced.update(turn.files_modified)
                conversation_log.append(
                    f"## Turn {turn.turn}\n"
                    f"**Squid:** {current_prompt}\n\n"
                    f"**OpenCode:**\n{turn.response_text}\n\n"
                )

                # Read expected output file
                output_content = ""
                try:
                    output_content = await self._manager.read_file(
                        self._agent_id, self._session_id, task.expected_output_file
                    )
                except FileNotFoundError:
                    pass

                review = _review_output(task, turn, output_content)
                conversation_log.append(
                    f"**Review:** {'SATISFIED' if review.satisfied else 'NEEDS MORE'}"
                    f" — {review.reason}\n\n"
                )

                if review.satisfied:
                    satisfied = True
                    status = "completed"
                    break

                # Check workspace output size limit before next turn
                workspace_size_kb = await self._workspace_size_kb()
                max_kb = self._manager._config.workspace_opencode_max_output_size_kb
                if workspace_size_kb > max_kb:
                    conversation_log.append(
                        f"**LIMIT:** Workspace size {workspace_size_kb}KB "
                        f"exceeds {max_kb}KB — stopping early.\n\n"
                    )
                    status = "output_limit_reached"
                    break

                current_prompt = review.followup_instruction

            if not satisfied and status == "abandoned":
                status = "completed"  # exhausted iterations, not an error

        except Exception as exc:
            status = "failed"
            conversation_log.append(f"**ERROR:** {exc}\n\n")
            raise
        finally:
            await session.close()
            loop_result = OpenCodeLoopResult(
                opencode_session_id=session.session_id,
                topic=task.topic,
                satisfied=satisfied,
                status=status,
                total_iterations=total_iterations,
                files_produced=list(files_produced),
                accumulated_usage=session.accumulated_usage,
            )
            await self._registry.update(
                session.session_id, status=status, result=loop_result
            )
            await self._manager.append_file(
                self._agent_id,
                self._session_id,
                "logs/opencode_conversation.md",
                "\n".join(conversation_log) + "\n---\n",
            )

        await self._bus.publish(Event(
            event_type=EventType.WORKSPACE_OPENCODE_TASK_COMPLETED,
            agent_id=self._agent_id,
            session_id=self._session_id,
            payload={
                "topic": task.topic,
                "satisfied": satisfied,
                "status": status,
                "iterations": total_iterations,
                "cost_usd": session.accumulated_usage.cost_usd,
            },
        ))
        return loop_result

    # ── Experiment Submission ─────────────────────────────────────────

    async def submit_experiment(
        self,
        hypothesis_id: str,
        spec: "ExperimentSpec",
        workspace_script_path: str | None = None,
    ) -> str:
        """
        Submit an experiment to the institutional pipeline.

        Returns experiment_id. Workspace-submitted experiments are tagged
        [workspace_exploration] and are treated as preliminary until an
        ExperimentResult validates them (see D10 in implementation plan).
        """
        exp_id = await self._submitter.submit(
            agent_id=self._agent_id,
            session_id=self._session_id,
            hypothesis_id=hypothesis_id,
            spec=spec,
            workspace_script_path=workspace_script_path,
        )
        from src.models.events import Event, EventType
        await self._bus.publish(Event(
            event_type=EventType.WORKSPACE_EXPERIMENT_SUBMITTED,
            agent_id=self._agent_id,
            session_id=self._session_id,
            artifact_id=exp_id,
            payload={"hypothesis_id": hypothesis_id},
        ))
        return exp_id

    # ── Shared Data Read ──────────────────────────────────────────────

    async def read_source_file(self, source_path: str) -> str:
        """
        Read from data/sources/ (shared read-only institutional data).

        Enforces that the path stays within the configured data_dir.
        """
        import asyncio
        from pathlib import Path
        data_root = Path(self._manager._config.data_dir)
        candidate = (data_root / source_path).resolve()
        if not str(candidate).startswith(str(data_root)):
            raise PermissionError(
                f"Path '{source_path}' escapes data/sources/. "
                "Only paths within the configured data_dir are readable."
            )
        return await asyncio.to_thread(candidate.read_text, encoding="utf-8")

    # ── Internal helpers ──────────────────────────────────────────────

    async def _workspace_size_kb(self) -> int:
        """Return total size of files in the workspace in KB."""
        import asyncio
        root = self._manager.workspace_root(self._agent_id, self._session_id)

        def _size() -> int:
            total = sum(
                p.stat().st_size
                for p in root.rglob("*")
                if p.is_file()
            )
            return total // 1024

        return await asyncio.to_thread(_size)
