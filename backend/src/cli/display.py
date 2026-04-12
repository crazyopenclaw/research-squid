"""Enhanced Rich console display for the CLI.

Architecture:
- DisplayManager coordinates all output and the Live status panel
- Event renderers dispatched via _EVENT_RENDERERS dict
- Action renderers dispatched via _ACTION_RENDERERS dict
- Agent Status Panel shows active agents with spinner animation
- Source Progress Panel shows download/ingestion progress
- All events use compact ┊ activity-feed format with agent colors + icons
- Important events auto-expand into detail panels
"""

from __future__ import annotations

import json
import time
from datetime import datetime
import time
from dataclasses import dataclass, field
from typing import Callable

from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from src.models.events import Event, EventType

console = Console()

# ── Constants ──────────────────────────────────────────────────────────────

EVENT_COLORS = {
    EventType.RESEARCH_STARTED: "bold green",
    EventType.RESEARCH_COMPLETED: "bold green",
    EventType.AGENT_SPAWNED: "cyan",
    EventType.AGENT_THINKING: "dim cyan",
    EventType.AGENT_ACTION: "blue",
    EventType.SOURCE_INGESTED: "yellow",
    EventType.SOURCE_DISCOVERED: "yellow",
    EventType.EXPERIMENT_STARTED: "magenta",
    EventType.EXPERIMENT_COMPLETED: "green",
    EventType.EXPERIMENT_FAILED: "red",
    EventType.ARTIFACT_CREATED: "dim white",
    EventType.ARTIFACT_REFUTED: "bold red",
    EventType.RELATION_CREATED: "dim blue",
    EventType.MESSAGE_SENT: "dim cyan",
    EventType.ITERATION_STARTED: "bold white",
    EventType.ITERATION_COMPLETED: "bold white",
    EventType.DEBATE_STARTED: "bold magenta",
    EventType.DEBATE_COMPLETED: "bold magenta",
    EventType.ERROR: "bold red",
    EventType.BUDGET_WARNING: "bold yellow",
    EventType.STATE_SNAPSHOT: "dim white",
    EventType.ARTIFACT_UPDATED: "dim white",
    EventType.EXPERIMENT_QUEUED: "dim magenta",
    EventType.CLUSTERS_COMPUTED: "dim cyan",
    EventType.INTRA_CLUSTER_REVIEW_STARTED: "cyan",
    EventType.INTRA_CLUSTER_REVIEW_PROGRESS: "dim cyan",
    EventType.INTRA_CLUSTER_REVIEW_COMPLETED: "cyan",
    EventType.INTER_CLUSTER_DEBATE_STARTED: "magenta",
    EventType.INTER_CLUSTER_DEBATE_PROGRESS: "dim magenta",
    EventType.INTER_CLUSTER_DEBATE_COMPLETED: "magenta",
    EventType.COUNTER_RESPONSES_STARTED: "dim magenta",
    EventType.COUNTER_RESPONSE_PROGRESS: "dim magenta",
    EventType.COUNTER_RESPONSES_COMPLETED: "dim magenta",
    EventType.ADJUDICATION_STARTED: "yellow",
    EventType.ADJUDICATION_PROGRESS: "dim yellow",
    EventType.ADJUDICATION_COMPLETED: "yellow",
    EventType.ADJUDICATING_HYPOTHESIS: "yellow",
    EventType.WORKSPACE_CREATED: "bold blue",
    EventType.WORKSPACE_FILE_WRITTEN: "blue",
    EventType.WORKSPACE_SCRIPT_EXECUTED: "dim blue",
    EventType.WORKSPACE_SCRIPT_FAILED: "red",
    EventType.WORKSPACE_MEMORY_UPDATED: "green",
    EventType.WORKSPACE_EXPERIMENT_SUBMITTED: "magenta",
    EventType.WORKSPACE_SNAPSHOTTED: "dim white",
    EventType.WORKSPACE_OPENCODE_SERVER_STARTED: "bold cyan",
    EventType.WORKSPACE_OPENCODE_TASK_COMPLETED: "cyan",
    EventType.WORKSPACE_OPENCODE_UNAVAILABLE: "yellow",
}

AGENT_PALETTE = [
    "cyan", "green", "magenta", "yellow", "blue",
    "bright_cyan", "bright_green", "bright_magenta",
    "bright_yellow", "bright_blue",
]

SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

STATE_ICONS = {
    "thinking": "💭",
    "working": "⚡",
    "idle": "○",
    "done": "✓",
    "error": "✖",
}

EVENT_ICONS = {
    EventType.RESEARCH_STARTED: "🔍",
    EventType.RESEARCH_COMPLETED: "✅",
    EventType.AGENT_SPAWNED: "🦑",
    EventType.AGENT_THINKING: "💭",
    EventType.AGENT_ACTION: "⚡",
    EventType.SOURCE_INGESTED: "📄",
    EventType.SOURCE_DISCOVERED: "🔎",
    EventType.EXPERIMENT_STARTED: "🧪",
    EventType.EXPERIMENT_COMPLETED: "✅",
    EventType.EXPERIMENT_FAILED: "❌",
    EventType.EXPERIMENT_QUEUED: "🧪",
    EventType.ARTIFACT_CREATED: "✦",
    EventType.ARTIFACT_UPDATED: "✎",
    EventType.ARTIFACT_REFUTED: "✖",
    EventType.RELATION_CREATED: "🔗",
    EventType.MESSAGE_SENT: "📨",
    EventType.ITERATION_STARTED: "▶",
    EventType.ITERATION_COMPLETED: "■",
    EventType.DEBATE_STARTED: "⚔️",
    EventType.DEBATE_COMPLETED: "⚔️",
    EventType.BUDGET_WARNING: "⚠️",
EventType.ERROR: "💥",
    EventType.STATE_SNAPSHOT: "📊",
    EventType.CLUSTERS_COMPUTED: "🔄",
    EventType.INTRA_CLUSTER_REVIEW_STARTED: "🔎",
    EventType.INTRA_CLUSTER_REVIEW_PROGRESS: "🔎",
    EventType.INTRA_CLUSTER_REVIEW_COMPLETED: "✅",
    EventType.INTER_CLUSTER_DEBATE_STARTED: "⚔️",
    EventType.INTER_CLUSTER_DEBATE_PROGRESS: "⚔️",
    EventType.INTER_CLUSTER_DEBATE_COMPLETED: "✅",
    EventType.COUNTER_RESPONSES_STARTED: "💬",
    EventType.COUNTER_RESPONSE_PROGRESS: "💬",
    EventType.COUNTER_RESPONSES_COMPLETED: "✅",
    EventType.ADJUDICATION_STARTED: "⚖️",
    EventType.ADJUDICATION_PROGRESS: "⚖️",
    EventType.ADJUDICATION_COMPLETED: "✅",
    EventType.ADJUDICATING_HYPOTHESIS: "⚖️",
    EventType.WORKSPACE_CREATED: "📁",
    EventType.WORKSPACE_FILE_WRITTEN: "📝",
    EventType.WORKSPACE_SCRIPT_EXECUTED: "▶",
    EventType.WORKSPACE_SCRIPT_FAILED: "❌",
    EventType.WORKSPACE_MEMORY_UPDATED: "🧠",
    EventType.WORKSPACE_EXPERIMENT_SUBMITTED: "🧪",
    EventType.WORKSPACE_SNAPSHOTTED: "📸",
    EventType.WORKSPACE_OPENCODE_SERVER_STARTED: "🖥️",
    EventType.WORKSPACE_OPENCODE_TASK_COMPLETED: "✅",
    EventType.WORKSPACE_OPENCODE_UNAVAILABLE: "⚠️",
}

ACTION_ICONS = {
    "decomposed_question": "🎯",
    "decomposition_started": "🎯",
    "decomposition_completed": "🎯",
    "archetype_design_started": "🏗️",
    "archetype_design_completed": "🏗️",
    "reclustered": "🔄",
    "downloading_source": "⬇️",
    "download_source_progress": "⬇️",
    "ingesting_source": "📥",
    "ingested_search_source": "📄",
    "search_source_already_ingested": "♻️",
    "reviewing_hypothesis": "👁️",
    "reviewed_hypothesis": "👁️",
    "intra_cluster_review_started": "🔎",
    "intra_cluster_review_progress": "🔎",
    "intra_cluster_review_completed": "✅",
    "inter_cluster_debate_started": "⚔️",
    "inter_cluster_debate_progress": "⚔️",
    "inter_cluster_debate_completed": "✅",
    "counter_responses_started": "💬",
    "counter_response_progress": "💬",
    "counter_responses_completed": "✅",
    "adjudication_started": "⚖️",
    "adjudicating_hypothesis": "⚖️",
    "adjudication_progress": "⚖️",
    "adjudication_completed": "✅",
}

RELATION_COLORS = {
    "SUPPORTS": "green",
    "EXTENDS": "cyan",
    "CONTRADICTS": "bold red",
    "REFUTES": "red",
    "QUESTIONS": "yellow",
    "DEPENDS_ON": "magenta",
    "DERIVED_FROM": "blue",
}

MESSAGE_COLORS = {
    "QUESTION": "yellow",
    "OBJECTION": "bold red",
    "EVIDENCE": "green",
    "ACKNOWLEDGMENT": "cyan",
    "REPLICATION_REQUEST": "magenta",
    "DEPENDENCY_WARNING": "bold yellow",
}

VERDICT_COLORS = {
    "support": "green",
    "challenge": "bold red",
    "extend": "cyan",
    "refute": "red",
}

SOURCE_PROGRESS_ACTIONS = {
    "downloading_source",
    "download_source_progress",
    "ingesting_source",
    "ingested_search_source",
    "search_source_already_ingested",
}

EXPAND_ARTIFACT_TYPES = {"hypothesis"}

# ── Agent Tracking ─────────────────────────────────────────────────────────

_agent_color_map: dict[str, str] = {}
_agent_color_idx: int = 0

AGENT_NAME_BY_ID: dict[str, str] = {
    "system": "System",
    "director": "Director",
    "controller": "Controller",
    "debate-system": "Debate System",
    "adjudicator": "Adjudicator",
}


def _agent_color(agent_id: str) -> str:
    if agent_id not in _agent_color_map:
        global _agent_color_idx
        _agent_color_map[agent_id] = AGENT_PALETTE[_agent_color_idx % len(AGENT_PALETTE)]
        _agent_color_idx += 1
    return _agent_color_map[agent_id]


def _remember_agent_name(agent_id: str, payload: dict) -> None:
    name = str(payload.get("name") or "").strip()
    if agent_id and name:
        AGENT_NAME_BY_ID[agent_id] = name


def _agent_name(agent_id: str | None) -> str:
    if not agent_id:
        return "System"
    return AGENT_NAME_BY_ID.get(agent_id, agent_id)


# ── Timing ─────────────────────────────────────────────────────────────────

_agent_timers: dict[str, float] = {}
_research_start: float | None = None


def _start_timer(agent_id: str) -> None:
    _agent_timers[agent_id] = time.monotonic()


def _elapsed(agent_id: str) -> str:
    start = _agent_timers.get(agent_id)
    if not start:
        return ""
    seconds = time.monotonic() - start
    if seconds < 1:
        return ""
    if seconds < 60:
        return f" ({seconds:.1f}s)"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f" ({minutes}m{secs:.0f}s)"


# ── Utility Helpers ────────────────────────────────────────────────────────


def _short(text: str | None, limit: int = 140) -> str:
    value = (text or "").strip().replace("\n", " ")
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _kv(payload: dict, keys: list[str]) -> str:
    parts: list[str] = []
    for key in keys:
        value = payload.get(key)
        if value not in (None, "", [], {}):
            parts.append(f"{key.replace('_', ' ')}={value}")
    return ", ".join(parts)


def _print_bullets(items: list[str], limit: int = 4) -> None:
    shown = 0
    for item in items[:limit]:
        text = str(item or "").strip()
        if not text:
            continue
        console.print(f"    - {_short(text, 180)}")
        shown += 1
    remaining = len(items) - shown
    if remaining > 0:
        console.print(f"    [dim]... {remaining} more[/]")


def _relation_endpoint(payload: dict, side: str) -> str:
    preview = str(payload.get(f"{side}_preview") or "").strip()
    if preview:
        return _short(preview, 100)
    text = str(payload.get(f"{side}_text") or "").strip()
    if text:
        return _short(text, 100)
    artifact_id = str(
        payload.get(f"{side}_id")
        or payload.get(f"{side}_artifact_id")
        or ""
    ).strip()
    artifact_type = str(payload.get(f"{side}_type") or "").strip()
    short_id = artifact_id[:12] + "..." if artifact_id else ""
    if artifact_type and short_id:
        return f"{artifact_type} {short_id}"
    return short_id


def _badge(text: str, palette: dict[str, str], fallback: str = "white") -> str:
    label = str(text or "").upper()
    color = palette.get(label, fallback)
    return f"[{color}][{label}][/{color}]"


def _progress_bar(progress: int, width: int = 18) -> str:
    clamped = max(0, min(100, int(progress)))
    filled = round(width * clamped / 100)
    return "[" + ("█" * filled) + ("░" * (width - filled)) + f"] {clamped:>3d}%"


def _json_preview(data: object, limit: int = 160) -> str:
    if data in (None, "", {}, []):
        return ""
    try:
        text = json.dumps(data, ensure_ascii=False, sort_keys=True)
    except TypeError:
        text = str(data)
    return _short(text, limit)


def _code_preview(code: str, limit: int = 180) -> str:
    cleaned = " ".join(line.strip() for line in str(code or "").splitlines() if line.strip())
    return _short(cleaned, limit)


def _activity_line(icon: str, agent_id: str, verb: str, detail: str, duration: str = "") -> str:
    color = _agent_color(agent_id or "system")
    name = _agent_name(agent_id)
    dur = duration if duration else _elapsed(agent_id or "system")
    return f"  [{color}]┊[/] {icon} [{color}]{name}[/] {verb}: {detail}{dur}"


def _activity_line_raw(icon: str, verb: str, detail: str, color: str = "white") -> str:
    return f"  [{color}]┊[/] {icon} [{color}]{verb}[/]: {detail}"


# ── Source Progress ─────────────────────────────────────────────────────────


class SourceProgressPanel:
    def __init__(self):
        self._rows: dict[str, str] = {}

    def update(self, key: str, line: str) -> None:
        self._rows[key] = line

    def finish(self, key: str) -> None:
        self._rows.pop(key, None)

    def is_active(self) -> bool:
        return bool(self._rows)

    def render(self) -> Table:
        table = Table.grid(expand=True)
        for row in self._rows.values():
            table.add_row(_short(row, max(40, console.width - 8)))
        return table


def _source_progress_key(agent_id: str, payload: dict) -> str:
    return "|".join([
        agent_id,
        str(payload.get("arxiv_id") or "").strip(),
        str(payload.get("source_id") or "").strip(),
        str(payload.get("title") or "").strip(),
    ])


def _size_text(payload: dict) -> str:
    total_bytes = payload.get("total_bytes")
    if not total_bytes:
        return ""
    downloaded_mb = float(payload.get("bytes_downloaded", 0) or 0) / (1024 * 1024)
    total_mb = float(total_bytes) / (1024 * 1024)
    return f" | {downloaded_mb:.2f}/{total_mb:.2f} MB"


def _render_source_progress_line(agent: str, payload: dict, action: str) -> str:
    title = _short(payload.get("title", ""), 48)
    if action == "downloading_source":
        progress = 0
        stage = "starting"
        prefix = f"{agent} downloading arXiv PDF"
    elif action == "download_source_progress":
        progress = int(payload.get("progress", 0) or 0)
        stage = str(payload.get("stage", "downloading")).replace("_", " ")
        prefix = f"{agent} downloading arXiv PDF"
    elif action == "ingesting_source":
        progress = int(payload.get("progress", 100) or 100)
        stage = "ingesting"
        prefix = f"{agent} ingesting arXiv PDF"
    elif action == "ingested_search_source":
        progress = 100
        stage = "ingested"
        prefix = f"{agent} ingested arXiv PDF"
    else:
        progress = 100
        stage = "reused"
        prefix = f"{agent} reused arXiv paper"
    return (
        f"  {prefix}: {title} "
        f"{_progress_bar(progress)} ({stage})"
        f"{_size_text(payload)}"
    )


# ── Agent Status Panel ─────────────────────────────────────────────────────


@dataclass
class AgentInfo:
    name: str
    color: str
    status: str = "idle"
    detail: str = ""
    start_time: float = field(default_factory=time.monotonic)


class AgentStatusPanel:
    def __init__(self):
        self._agents: dict[str, AgentInfo] = {}
        self._frame: int = 0

    def spawn(self, agent_id: str, name: str, detail: str = "") -> None:
        color = _agent_color(agent_id)
        self._agents[agent_id] = AgentInfo(
            name=name, color=color, status="idle", detail=detail
        )

    def update_status(self, agent_id: str, status: str, detail: str = "") -> None:
        if agent_id in self._agents:
            if status == "thinking":
                self._agents[agent_id].start_time = time.monotonic()
            self._agents[agent_id].status = status
            self._agents[agent_id].detail = detail

    def remove(self, agent_id: str) -> None:
        self._agents.pop(agent_id, None)

    def tick(self) -> None:
        self._frame = (self._frame + 1) % len(SPINNER_FRAMES)

    def is_active(self) -> bool:
        return bool(self._agents)

    def render(self) -> Table:
        self.tick()
        table = Table.grid(expand=True, padding=(0, 1))
        table.add_column(width=1)
        table.add_column()
        for info in self._agents.values():
            if info.status == "thinking":
                icon = SPINNER_FRAMES[self._frame]
            else:
                icon = STATE_ICONS.get(info.status, "○")
            elapsed = ""
            if info.status in ("thinking", "working"):
                seconds = time.monotonic() - info.start_time
                if seconds >= 1:
                    if seconds < 60:
                        elapsed = f" ({seconds:.0f}s)"
                    else:
                        elapsed = f" ({int(seconds // 60)}m{seconds % 60:.0f}s)"
            detail_str = f" {info.detail}" if info.detail else ""
            table.add_row(
                f"[{info.color}]{icon}[/]",
                f"[{info.color}]{info.name}[/]{elapsed}{detail_str}",
            )
        return table


# ── Display Manager ─────────────────────────────────────────────────────────


class DisplayManager:
    def __init__(self):
        self._live: Live | None = None
        self.agents = AgentStatusPanel()
        self.sources = SourceProgressPanel()
        self._budget_total: float | None = None

    def start(self) -> None:
        if self._live is not None:
            return
        self._live = Live(
            self._render_status(),
            console=console,
            refresh_per_second=4,
            transient=True,
        )
        self._live.start()

    def stop(self) -> None:
        if self._live is not None:
            self._live.stop()
            self._live = None

    def _print(self, *args, **kwargs) -> None:
        if args and isinstance(args[0], str):
            ts = datetime.now().strftime("[%H:%M:%S]")
            args = (f"[dim]{ts}[/] " + args[0],) + args[1:]
        
        if self._live is not None:
            self._live.console.print(*args, **kwargs)
        else:
            console.print(*args, **kwargs)

    def _refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._render_status())

    def _render_status(self) -> Panel:
        sections: list = []
        if self.agents.is_active():
            sections.append(self.agents.render())
        if self.sources.is_active():
            sections.append(self.sources.render())
        if sections:
            return Panel(
                Group(*sections),
                title="🦑 Research",
                border_style="dim",
                expand=False,
            )
        return Panel("starting...", title="🦑 Research", border_style="dim", expand=False)

    def handle_event(self, event: Event) -> None:
        _remember_agent_name(event.agent_id or "system", event.payload or {})
        color = EVENT_COLORS.get(event.event_type, "white")
        agent_id = event.agent_id or "system"
        payload = event.payload or {}

        if event.event_type == EventType.RESEARCH_STARTED:
            _agent_color_map.clear()
            _agent_color_idx = 0
            global _research_start
            _research_start = time.monotonic()

        if event.event_type == EventType.AGENT_SPAWNED:
            name = str(payload.get("name") or "").strip()
            if not name:
                name = _agent_name(agent_id)
            self.agents.spawn(agent_id, name, str(payload.get("inquiry", "")))

        if event.event_type in (
            EventType.AGENT_THINKING,
            EventType.AGENT_ACTION,
        ):
            status = "thinking" if event.event_type == EventType.AGENT_THINKING else "working"
            detail = ""
            if event.event_type == EventType.AGENT_THINKING:
                detail = _short(payload.get("inquiry", ""), 40)
            elif event.event_type == EventType.AGENT_ACTION:
                action = str(payload.get("action") or "").strip()
                if action:
                    detail = action.replace("_", " ")
            self.agents.update_status(agent_id, status, detail)
            if event.event_type == EventType.AGENT_THINKING:
                _start_timer(agent_id)

        renderer = _EVENT_RENDERERS.get(event.event_type)
        if renderer:
            renderer(event, self)
        else:
            _render_unknown(event, self)

        self._refresh()


# ── Event Renderers ─────────────────────────────────────────────────────────

_EVENT_RENDERERS: dict[EventType, Callable] = {}


def _renders(event_type: EventType):
    def decorator(fn):
        _EVENT_RENDERERS[event_type] = fn
        return fn
    return decorator


@_renders(EventType.RESEARCH_STARTED)
def _render_research_started(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    question = payload.get("question", "")
    dm._print(Panel(
        f"[bold]{question}[/bold]",
        title="🔍 Research Started",
        border_style="green",
    ))


@_renders(EventType.RESEARCH_COMPLETED)
def _render_research_completed(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    iterations = payload.get("iterations", 0)
    budget_used = payload.get("budget_used", 0.0)
    budget_total = dm._budget_total
    budget_info = f"${budget_used:.2f}"
    if budget_total:
        pct = budget_used / budget_total * 100 if budget_total > 0 else 0
        budget_info = f"${budget_used:.2f}/${budget_total:.2f} ({pct:.0f}%)"

    elapsed = ""
    global _research_start
    if _research_start:
        seconds = time.monotonic() - _research_start
        if seconds < 60:
            elapsed = f"  ⏱ {seconds:.1f}s"
        else:
            elapsed = f"  ⏱ {int(seconds // 60)}m{seconds % 60:.0f}s"

    dm._print(Panel(
        f"Iterations: {iterations}\n"
        f"Spend: {budget_info}{elapsed}",
        title="✅ Research Complete",
        border_style="green",
    ))


@_renders(EventType.AGENT_SPAWNED)
def _render_agent_spawned(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    name = str(payload.get("name") or _agent_name(agent_id))
    inquiry = str(payload.get("inquiry", "")).strip()
    color = _agent_color(agent_id)
    line = f"  [{color}]┊ 🦑 [{color}]{name}[/] spawned"
    if inquiry:
        line += f": {_short(inquiry, 120)}"
    line += "[/]"
    dm._print(line)


@_renders(EventType.AGENT_THINKING)
def _render_agent_thinking(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    inquiry = _short(payload.get("inquiry", ""))
    dm._print(_activity_line("💭", agent_id, "thinking about", inquiry))


@_renders(EventType.AGENT_ACTION)
def _render_agent_action(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    action = str(payload.get("action") or "").strip()
    renderer = _ACTION_RENDERERS.get(action)
    if renderer:
        renderer(event, dm)
    else:
        icon = ACTION_ICONS.get(action, "⚡")
        color = _agent_color(agent_id)
        name = _agent_name(agent_id)
        if action:
            detail = _kv(payload, [k for k in payload.keys() if k != "action"])
            dm._print(f"  [{color}]┊[/] {icon} [{color}]{name}[/] {action}: {detail}")
        else:
            summary = _kv(payload, ["notes", "hypotheses", "relations", "experiments"])
            if summary:
                if all((payload.get(key, 0) == 0) for key in ["notes", "hypotheses", "relations", "experiments"]):
                    dm._print(f"  [{color}]┊[/] {icon} [{color}]{name}[/] produced no new artifacts this pass")
                else:
                    dm._print(f"  [{color}]┊[/] {icon} [{color}]{name}[/]: {summary}")


@_renders(EventType.SOURCE_INGESTED)
def _render_source_ingested(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    title = _short(payload.get("title", ""), 80)
    chunks = payload.get("chunks_count", 0)
    dm._print(_activity_line_raw("📄", "Ingested", f"{title} ({chunks} chunks)"))


@_renders(EventType.SOURCE_DISCOVERED)
def _render_source_discovered(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    source_name = str(payload.get("source", "")).strip()
    results_count = payload.get("results_count", 0)
    query = _short(payload.get("query", ""), 90)
    if source_name == "arxiv":
        detail = f"{results_count} arXiv papers: {query}"
        dm._print(_activity_line_raw("🔎", "Discovered", detail))
        for title in payload.get("titles", [])[:3]:
            dm._print(f"    - {_short(title, 120)}")
    else:
        detail = f"{results_count} results from {source_name}: {query}"
        dm._print(_activity_line_raw("🔎", "Discovered", detail))


@_renders(EventType.EXPERIMENT_STARTED)
def _render_experiment_started(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    extra = ""
    if payload.get("hypothesis_id"):
        extra = f" for hypothesis {str(payload.get('hypothesis_id'))[:12]}..."
    artifact = event.artifact_id[:12] if event.artifact_id else "?"
    dm._print(_activity_line("🧪", agent_id, "experiment started", f"{artifact}{extra}"))
    if payload.get("expected_outcome"):
        dm._print(f"    expected: {_short(payload.get('expected_outcome', ''), 140)}")
    if payload.get("input_data") not in (None, {}, []):
        dm._print(f"    inputs:   {_json_preview(payload.get('input_data'))}")
    if payload.get("code_preview"):
        dm._print(f"    code:     {_code_preview(payload.get('code_preview', ''))}")


@_renders(EventType.EXPERIMENT_COMPLETED)
def _render_experiment_completed(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    exit_code = payload.get("exit_code", "?")
    status = "PASS" if exit_code == 0 else f"EXIT {exit_code}"
    artifact = event.artifact_id[:12] if event.artifact_id else "?"
    dm._print(_activity_line("✅", agent_id, f"experiment {status}", artifact))
    if payload.get("stdout_preview"):
        dm._print(f"    output: {_short(payload.get('stdout_preview', ''), 150)}")
    if payload.get("stderr_preview"):
        dm._print(f"    stderr: {_short(payload.get('stderr_preview', ''), 150)}")
    if payload.get("artifacts") not in (None, {}, []):
        dm._print(f"    results: {_json_preview(payload.get('artifacts'))}")
    if payload.get("input_data") not in (None, {}, []):
        dm._print(f"    inputs:  {_json_preview(payload.get('input_data'))}")


@_renders(EventType.EXPERIMENT_FAILED)
def _render_experiment_failed(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    color = EVENT_COLORS.get(event.event_type, "white")
    error = _short(payload.get("error", ""), 180)
    code_suffix = ""
    if payload.get("exit_code") not in (None, ""):
        code_suffix = f" (exit {payload.get('exit_code')})"
    line = f"  [{color}]┊ ❌ Experiment FAILED{code_suffix}:[/] {error}"
    dm._print(line)
    if payload.get("expected_outcome"):
        dm._print(f"    expected: {_short(payload.get('expected_outcome', ''), 140)}")
    if payload.get("input_data") not in (None, {}, []):
        dm._print(f"    inputs:   {_json_preview(payload.get('input_data'))}")
    if payload.get("code_preview"):
        dm._print(f"    code:     {_code_preview(payload.get('code_preview', ''))}")
    if payload.get("stdout_preview"):
        dm._print(f"    output:   {_short(payload.get('stdout_preview', ''), 150)}")


@_renders(EventType.EXPERIMENT_QUEUED)
def _render_experiment_queued(event: Event, dm: DisplayManager) -> None:
    agent_id = event.agent_id or "system"
    artifact = event.artifact_id[:12] if event.artifact_id else "?"
    dm._print(_activity_line("🧪", agent_id, "experiment queued", artifact))


@_renders(EventType.ITERATION_STARTED)
def _render_iteration_started(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    iteration = payload.get("iteration", 0)
    phase = payload.get("phase", "research")
    budget_remaining = payload.get("budget_remaining_usd")
    budget_total = payload.get("budget_total_usd")
    if budget_total:
        dm._budget_total = budget_total

    budget_str = ""
    if budget_remaining is not None and budget_total:
        spent = budget_total - budget_remaining
        pct = spent / budget_total * 100 if budget_total > 0 else 0
        budget_str = f"  │  💰 ${spent:.2f}/${budget_total:.2f} {_progress_bar(int(pct), 16)}"

    dm._print(Rule(
        f"  ▶ ITERATION {iteration} — {str(phase).upper()}  ",
        style="bold white",
    ))
    if budget_str:
        dm._print(f"  {budget_str}")
    dm._print("")


@_renders(EventType.ITERATION_COMPLETED)
def _render_iteration_completed(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    iteration = payload.get("iteration", 0)
    should_stop = payload.get("should_stop", False)
    status_text = "STOPPING" if should_stop else "CONTINUING"
    status_icon = "■" if should_stop else "▶"
    dm._print(f"\n  ┊ {status_icon} Iteration {iteration} complete - [bold]{status_text}[/]")
    if payload.get("reasoning"):
        dm._print(f"    reasoning: {_short(payload.get('reasoning', ''), 200)}")
    for directive in payload.get("directives", []):
        dm._print(f"    > {directive}")


@_renders(EventType.DEBATE_STARTED)
def _render_debate_started(event: Event, dm: DisplayManager) -> None:
    dm._print(f"\n  ┊ ⚔️  Debate round starting...")


@_renders(EventType.DEBATE_COMPLETED)
def _render_debate_completed(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    contradictions = payload.get("contradictions_found", 0)
    dm._print(f"  ┊ ⚔️  Debate complete: {contradictions} contradictions found")


@_renders(EventType.ARTIFACT_CREATED)
def _render_artifact_created(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    artifact_type = str(event.artifact_type or payload.get("label", "")).lower()

    if artifact_type in {"source", "sourcechunk", "source_chunk", "relation", "message"}:
        return

    icon = "✦"
    verb = "created"
    detail = _short(payload.get("text", ""), 170)
    color = _agent_color(agent_id)
    name = _agent_name(agent_id)

    if artifact_type == "note":
        dm._print(_activity_line(icon, agent_id, "note", _short(payload.get("text", ""), 170)))
    elif artifact_type == "assumption":
        basis = _short(payload.get("basis", ""), 90)
        suffix = f" (basis: {basis})" if basis else ""
        dm._print(_activity_line(icon, agent_id, "assumption", f"{_short(payload.get('text', ''), 150)}{suffix}"))
    elif artifact_type == "hypothesis":
        confidence = payload.get("confidence")
        confidence_text = f" (confidence {confidence:.2f})" if isinstance(confidence, (int, float)) else ""
        text = _short(payload.get("text", ""), 170)
        dm._print(_activity_line("💡", agent_id, f"hypothesis{confidence_text}", text))
        dm._print(Panel(
            f"[bold]Hypothesis[/] (confidence {confidence:.2f})\n\n"
            f"{payload.get('text', '')}\n"
            + (f"\n[dim]basis: {payload.get('basis', '')}[/]" if payload.get("basis") else ""),
            title=f"💡 {_agent_name(agent_id)}",
            border_style=_agent_color(agent_id),
            expand=False,
        ))
    elif artifact_type == "finding":
        conclusion = str(payload.get("conclusion_type", "")).strip()
        conclusion_text = f" [{conclusion}]" if conclusion else ""
        dm._print(_activity_line("💡", agent_id, f"finding{conclusion_text}", _short(payload.get("text", ""), 170)))
    elif artifact_type == "experiment":
        summary = _short(payload.get("expected_outcome", ""), 150) or _short(payload.get("code_preview", ""), 150)
        dm._print(_activity_line("🧪", agent_id, "experiment proposed", summary))
    elif artifact_type == "experimentresult":
        dm._print(f"  [{color}]┊[/] ✅ Experiment result: exit={payload.get('exit_code', '?')}, "
                   f"stdout={_short(payload.get('stdout_preview', ''), 120)}")
    else:
        artifact = event.artifact_id[:12] if event.artifact_id else "?"
        dm._print(f"  [{color}]┊[/] {icon} [{color}]{name}[/] created {artifact_type or 'artifact'}: {artifact}")


@_renders(EventType.ARTIFACT_REFUTED)
def _render_artifact_refuted(event: Event, dm: DisplayManager) -> None:
    color = EVENT_COLORS.get(event.event_type, "white")
    agent_id = event.agent_id or "system"
    agent = _agent_name(agent_id)
    artifact = event.artifact_id[:12] if event.artifact_id else "?"
    dm._print(f"  [{color}]┊ ✖ REFUTED:[/] {artifact} by {agent}")


@_renders(EventType.ARTIFACT_UPDATED)
def _render_artifact_updated(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    color = EVENT_COLORS.get(event.event_type, "white")
    updated_fields = payload.get("updated_fields", [])
    properties = payload.get("properties", {})
    label = str(payload.get("label", "")).strip()
    if updated_fields == ["read"] or updated_fields == ["embedding_id"]:
        return
    if sorted(updated_fields) == ["file_path", "source_type", "title", "uri"]:
        return
    if label == "Experiment" and "status" in properties:
        return
    artifact = event.artifact_id[:12] if event.artifact_id else "?"
    if "status" in properties:
        dm._print(f"  [{color}]┊ ✎ Status update:[/] {artifact} -> {properties.get('status', '?')}")
    elif "adjudication_status" in properties:
        dm._print(f"  [{color}]┊ ✎ Adjudication update:[/] {artifact} -> {properties.get('adjudication_status', '?')}")
    else:
        dm._print(f"  [{color}]┊ ✎ Artifact updated:[/] {artifact} {_kv(payload, ['updated_fields'])}")


@_renders(EventType.RELATION_CREATED)
def _render_relation_created(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    color = EVENT_COLORS.get(event.event_type, "white")
    agent = _agent_name(event.agent_id)
    rel_type = str(payload.get("relation_type", "relation")).upper()
    dm._print(f"  [{color}]┊ 🔗 {agent} relation {_badge(rel_type, RELATION_COLORS)}:")
    dm._print(f"    from: {_relation_endpoint(payload, 'source')}")
    dm._print(f"    to:   {_relation_endpoint(payload, 'target')}")
    if payload.get("reasoning"):
        dm._print(f"    why:  {_short(payload.get('reasoning', ''), 140)}")


@_renders(EventType.MESSAGE_SENT)
def _render_message_sent(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    to_agent = _agent_name(payload.get("to_agent"))
    message_type = str(payload.get("message_type", "message")).upper()
    text = _short(payload.get("text", ""), 170)
    dm._print(_activity_line("📨", agent_id, f"sent {_badge(message_type, MESSAGE_COLORS)} to {to_agent}", text))


@_renders(EventType.STATE_SNAPSHOT)
def _render_state_snapshot(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    if not payload:
        return
    interesting = _kv(payload, ["iteration", "status", "budget_remaining_usd", "budget_total_usd"])
    if interesting:
        dm._print(f"  ┊ 📊 State snapshot: {interesting}")


@_renders(EventType.BUDGET_WARNING)
def _render_budget_warning(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    pct = payload.get("percentage", 0)
    total = payload.get("budget_total_usd", 0)
    used = payload.get("dollars_used", 0)
    bar = _progress_bar(int(pct), 20)
    dm._print(f"  [bold yellow]┊ ⚠️  Budget warning: {pct:.0f}% used[/]  {bar}  ${used:.2f}/${total:.2f}")


@_renders(EventType.ERROR)
def _render_error(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    color = EVENT_COLORS.get(event.event_type, "white")
    error = payload.get("error", "Unknown error")
    dm._print(Panel(
        str(error),
        title="💥 Error",
        border_style="red",
    ))


# ── Workspace Event Renderers ──────────────────────────────────────────────


@_renders(EventType.WORKSPACE_CREATED)
def _render_workspace_created(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    path = _short(payload.get("path", ""), 60)
    dm._print(_activity_line("📁", agent_id, "workspace created", path))


@_renders(EventType.WORKSPACE_FILE_WRITTEN)
def _render_workspace_file_written(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    file_path = _short(payload.get("path", ""), 50)
    size = payload.get("size_bytes", 0)
    size_kb = size / 1024 if size else 0
    dm._print(_activity_line("📝", agent_id, "file written", f"{file_path} ({size_kb:.1f} KB)"))


@_renders(EventType.WORKSPACE_SCRIPT_EXECUTED)
def _render_workspace_script_executed(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    script = _short(payload.get("script", ""), 60)
    dm._print(_activity_line("▶", agent_id, "script executed", script))


@_renders(EventType.WORKSPACE_SCRIPT_FAILED)
def _render_workspace_script_failed(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    error = _short(payload.get("error", ""), 100)
    dm._print(_activity_line("❌", agent_id, "script failed", error))


@_renders(EventType.WORKSPACE_MEMORY_UPDATED)
def _render_workspace_memory_updated(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    auto_logged = payload.get("auto_logged", False)
    auto_tag = " (auto)" if auto_logged else ""
    iteration = payload.get("iteration", "?")
    dm._print(_activity_line("🧠", agent_id, f"memory updated{auto_tag}", f"iteration={iteration}"))
    if payload.get("issues"):
        for issue in payload.get("issues", [])[:2]:
            dm._print(f"    [dim]warning: {issue}[/]")


@_renders(EventType.WORKSPACE_EXPERIMENT_SUBMITTED)
def _render_workspace_experiment_submitted(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    hyp_id = _short(payload.get("hypothesis_id", ""), 12)
    dm._print(_activity_line("🧪", agent_id, "experiment submitted", f"hypothesis={hyp_id}"))


@_renders(EventType.WORKSPACE_SNAPSHOTTED)
def _render_workspace_snapshotted(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    path = _short(payload.get("snapshot_path", ""), 60)
    dm._print(_activity_line("📸", agent_id, "snapshotted", path))


@_renders(EventType.WORKSPACE_OPENCODE_SERVER_STARTED)
def _render_workspace_opencode_server_started(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    port = payload.get("port", "?")
    path = _short(payload.get("workspace", ""), 50)
    dm._print(_activity_line("🖥️", agent_id, "OpenCode server", f"port={port} path={path}"))


@_renders(EventType.WORKSPACE_OPENCODE_TASK_COMPLETED)
def _render_workspace_opencode_task_completed(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    satisfied = payload.get("satisfied", False)
    status_icon = "✓" if satisfied else "○"
    cost = payload.get("cost_usd", 0)
    topic = payload.get("topic", "untitled")
    iterations = payload.get("iterations", 0)
    dm._print(_activity_line("✅", agent_id, f"OpenCode task [{status_icon}]", f"{topic} ({iterations} turns, ${cost:.4f})"))


@_renders(EventType.WORKSPACE_OPENCODE_UNAVAILABLE)
def _render_workspace_opencode_unavailable(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    reason = payload.get("reason", "not installed")
    dm._print(f"  [yellow]┊ ⚠️  OpenCode unavailable:[/] {agent_id} ({reason})")


# ── Debate Event Renderers ──────────────────────────────────────────────────


@_renders(EventType.CLUSTERS_COMPUTED)
def _render_clusters_computed(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    clusters = payload.get("num_clusters", 0)
    dm._print(_activity_line("🔄", agent_id, "clusters computed", str(clusters)))


@_renders(EventType.INTRA_CLUSTER_REVIEW_STARTED)
def _render_intra_cluster_review_started(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    clusters = payload.get("clusters", 0)
    planned = payload.get("planned_reviews", 0)
    dm._print(_activity_line("🔎", agent_id, "intra-cluster review started", f"clusters={clusters}, planned_reviews={planned}"))
    for item in payload.get("review_plan_preview", [])[:5]:
        reviewer = _agent_name(item.get("reviewer_id"))
        peer = _agent_name(item.get("peer_id"))
        target = _short(item.get("hypothesis_text", ""), 120)
        dm._print(f"    {reviewer} [cyan]reviewing[/] {peer}'s hypothesis: {target}")


@_renders(EventType.INTRA_CLUSTER_REVIEW_PROGRESS)
def _render_intra_cluster_review_progress(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    reviewer = _agent_name(payload.get("reviewer_id"))
    peer = _agent_name(payload.get("peer_id"))
    completed = payload.get("completed_reviews", 0)
    total = payload.get("total_reviews", 0)
    failed = payload.get("failed_reviews", 0)
    target = _short(payload.get("hypothesis_text", ""), 100)
    dm._print(f"  ┊ 🔎 Review progress: {completed}/{total} complete, {failed} failed - "
              f"{reviewer} vs {peer}: {target}")


@_renders(EventType.INTRA_CLUSTER_REVIEW_COMPLETED)
def _render_intra_cluster_review_completed(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    completed = payload.get("completed_reviews", 0)
    failed = payload.get("failed_reviews", 0)
    experiments = payload.get("experiments_proposed", 0)
    dm._print(_activity_line("✅", agent_id, "intra-cluster review completed",
                             f"completed={completed}, failed={failed}, experiments={experiments}"))


@_renders(EventType.INTER_CLUSTER_DEBATE_STARTED)
def _render_inter_cluster_debate_started(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    pairs = payload.get("pairs", 0)
    dm._print(_activity_line("⚔️", agent_id, "inter-cluster debate started", f"pairs={pairs}"))
    for item in payload.get("pair_preview", [])[:5]:
        challenger = _agent_name(item.get("challenger_id"))
        owner = _agent_name(item.get("target_owner_id"))
        target = _short(item.get("target_hypothesis_text", ""), 130)
        if target:
            dm._print(f"    {challenger} [bold red]challenges[/] {owner}'s hypothesis: {target}")


@_renders(EventType.INTER_CLUSTER_DEBATE_PROGRESS)
def _render_inter_cluster_debate_progress(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    challenger = _agent_name(payload.get("challenger_id"))
    owner = _agent_name(payload.get("target_owner_id"))
    completed = payload.get("completed_pairs", 0)
    total = payload.get("total_pairs", 0)
    failed = payload.get("failed_pairs", 0)
    target = _short(payload.get("target_hypothesis_text", ""), 100)
    dm._print(f"  ┊ ⚔️  Debate progress: {completed}/{total} complete, {failed} failed - "
              f"{challenger} challenging {owner}: {target}")


@_renders(EventType.INTER_CLUSTER_DEBATE_COMPLETED)
def _render_inter_cluster_debate_completed(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    completed = payload.get("completed_pairs", 0)
    failed = payload.get("failed_pairs", 0)
    experiments = payload.get("experiments_proposed", 0)
    dm._print(_activity_line("✅", agent_id, "inter-cluster debate completed",
                             f"completed={completed}, failed={failed}, experiments={experiments}"))


@_renders(EventType.COUNTER_RESPONSES_STARTED)
def _render_counter_responses_started(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    challenged = payload.get("challenged_hypotheses", 0)
    dm._print(_activity_line("💬", agent_id, "counter-responses started", f"challenged={challenged}"))
    for item in payload.get("challenged_hypothesis_preview", [])[:4]:
        author = _agent_name(item.get("author_id"))
        reviewer = _agent_name(item.get("reviewer_id"))
        dm._print(f"    {author} responding to {reviewer}'s challenge on "
                  f"{_short(item.get('hypothesis_text', ''), 80)}")
        dm._print(f"      critique: {_short(item.get('critique', ''), 120)}")


@_renders(EventType.COUNTER_RESPONSE_PROGRESS)
def _render_counter_response_progress(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    author = _agent_name(payload.get("author_id"))
    reviewer = _agent_name(payload.get("reviewer_id"))
    completed = payload.get("completed_responses", 0)
    total = payload.get("total_responses", 0)
    failed = payload.get("failed_responses", 0)
    target = _short(payload.get("hypothesis_text", ""), 90)
    dm._print(f"  ┊ 💬 Counter-response progress: {completed}/{total} complete, {failed} failed - "
              f"{author} replying to {reviewer} on {target}")


@_renders(EventType.COUNTER_RESPONSES_COMPLETED)
def _render_counter_responses_completed(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    attempted = payload.get("responses_attempted", 0)
    failed = payload.get("failed_responses", 0)
    dm._print(_activity_line("✅", agent_id, "counter-responses completed",
                             f"attempted={attempted}, failed={failed}"))


@_renders(EventType.ADJUDICATION_STARTED)
def _render_adjudication_started(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    targets = payload.get("targets", 0)
    dm._print(_activity_line("⚖️", agent_id, "adjudication started", f"targets={targets}"))
    for item in payload.get("target_preview", [])[:5]:
        dm._print(f"    reviewing contested hypothesis: "
                  f"{_short(item.get('target_text', ''), 120)}")


@_renders(EventType.ADJUDICATING_HYPOTHESIS)
def _render_adjudicating_hypothesis(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    target = _short(payload.get("target_text", ""), 120)
    supporters = payload.get("supporters", 0)
    contradictors = payload.get("contradictors", 0)
    dm._print(_activity_line("⚖️", agent_id, "adjudicating",
                             f"{target} (support={supporters}, contradict={contradictors})"))


@_renders(EventType.ADJUDICATION_PROGRESS)
def _render_adjudication_progress(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    completed = payload.get("completed_targets", 0)
    total = payload.get("total_targets", 0)
    failed = payload.get("failed_targets", 0)
    target = _short(payload.get("target_text", ""), 100)
    ruling = _short(payload.get("ruling", ""), 70)
    dm._print(f"  ┊ ⚖️  Adjudication progress: {completed}/{total} complete, {failed} failed - "
              f"{target} => {ruling}")


@_renders(EventType.ADJUDICATION_COMPLETED)
def _render_adjudication_completed(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    targets = payload.get("targets", 0)
    failed = payload.get("failed_targets", 0)
    dm._print(_activity_line("✅", agent_id, "adjudication completed",
                             f"targets={targets}, failed={failed}"))


# ── Action Renderers (AGENT_ACTION sub-dispatch) ────────────────────────────

_ACTION_RENDERERS: dict[str, Callable] = {}


def _action(action_name: str):
    def decorator(fn):
        _ACTION_RENDERERS[action_name] = fn
        return fn
    return decorator


@_action("decomposed_question")
def _action_decomposed_question(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    subproblems = payload.get("subproblems_count", 0)
    archetypes = payload.get("archetypes_count", 0)
    dm._print(_activity_line("🎯", agent_id, "decomposed question",
                             f"subproblems={subproblems}, archetypes={archetypes}"))
    if payload.get("reasoning_summary"):
        dm._print(f"    rationale: {_short(payload.get('reasoning_summary', ''), 180)}")
    if payload.get("open_questions"):
        dm._print("    open questions:")
        _print_bullets(payload.get("open_questions", []))
    if payload.get("key_assumptions"):
        dm._print("    key assumptions:")
        _print_bullets(payload.get("key_assumptions", []))
    if payload.get("archetype_names"):
        dm._print(f"    archetypes: {_short(', '.join(payload.get('archetype_names', [])), 180)}")
    if payload.get("archetype_reasoning"):
        dm._print(f"    archetype rationale: {_short(payload.get('archetype_reasoning', ''), 180)}")


@_action("decomposition_started")
def _action_decomposition_started(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    dm._print(_activity_line("🎯", agent_id, "analyzing the research question",
                             _short(payload.get("question", ""), 180)))


@_action("decomposition_completed")
def _action_decomposition_completed(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    subproblems = payload.get("subproblems_count", 0)
    open_questions = payload.get("open_questions_count", 0)
    assumptions = payload.get("key_assumptions_count", 0)
    dm._print(_activity_line("🎯", agent_id, "research plan drafted",
                             f"subproblems={subproblems}, open_questions={open_questions}, assumptions={assumptions}"))
    if payload.get("reasoning_summary"):
        dm._print(f"    rationale: {_short(payload.get('reasoning_summary', ''), 180)}")


@_action("archetype_design_started")
def _action_archetype_design_started(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    target = payload.get("max_archetypes", 0)
    subproblems = payload.get("subproblems_count", 0)
    dm._print(_activity_line("🏗️", agent_id, "designing agent archetypes",
                             f"target={target}, subproblems={subproblems}"))


@_action("archetype_design_completed")
def _action_archetype_design_completed(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    count = payload.get("archetypes_count", 0)
    dm._print(_activity_line("🏗️", agent_id, "archetype design completed", f"count={count}"))
    if payload.get("archetype_names"):
        dm._print(f"    archetypes: {_short(', '.join(payload.get('archetype_names', [])), 180)}")
    if payload.get("reasoning_summary"):
        dm._print(f"    rationale: {_short(payload.get('reasoning_summary', ''), 180)}")


@_action("reclustered")
def _action_reclustered(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    num_clusters = payload.get("num_clusters", 0)
    sizes = payload.get("cluster_sizes", [])
    dm._print(_activity_line("🔄", agent_id, "reclustered",
                             f"{num_clusters} clusters, sizes={sizes}"))
    for cluster in payload.get("clusters", [])[:5]:
        names = ", ".join(
            member.get("name", member.get("agent_id", "?"))
            for member in cluster.get("members", [])
        )
        shared = len(cluster.get("shared_hypotheses", []))
        contested = len(cluster.get("contested_hypotheses", []))
        dm._print(f"    {cluster.get('cluster_id', 'cluster')}: {names} "
                  f"[dim](shared={shared}, contested={contested})[/]")


@_action("reviewed_hypothesis")
def _action_reviewed_hypothesis(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    verdict = str(payload.get("verdict", "")).lower()
    hyp_id = payload.get("hypothesis_id", "")[:12]
    text = _short(payload.get("hypothesis_text", ""), 120)
    dm._print(_activity_line("👁️", agent_id, f"reviewed hypothesis {hyp_id}...",
                             f"{_badge(verdict, VERDICT_COLORS)}: {text}"))


@_action("reviewing_hypothesis")
def _action_reviewing_hypothesis(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    owner = _agent_name(payload.get("created_by"))
    text = _short(payload.get("hypothesis_text", ""), 140)
    dm._print(_activity_line("👁️", agent_id, f"reviewing {owner}'s hypothesis", text))


@_action("downloading_source")
def _action_downloading_source(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    key = _source_progress_key(agent_id, payload)
    line = _render_source_progress_line(_agent_name(agent_id), payload, "downloading_source")
    dm.sources.update(key, line)


@_action("download_source_progress")
def _action_download_source_progress(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    key = _source_progress_key(agent_id, payload)
    line = _render_source_progress_line(_agent_name(agent_id), payload, "download_source_progress")
    dm.sources.update(key, line)


@_action("ingesting_source")
def _action_ingesting_source(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    key = _source_progress_key(agent_id, payload)
    line = _render_source_progress_line(_agent_name(agent_id), payload, "ingesting_source")
    dm.sources.update(key, line)


@_action("ingested_search_source")
def _action_ingested_search_source(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    color = _agent_color(agent_id)
    name = _agent_name(agent_id)
    key = _source_progress_key(agent_id, payload)
    dm.sources.finish(key)
    if payload.get("file_path"):
        dm._print(f"  [{color}]┊ 📄 [{color}]{name}[/] ingested arXiv PDF: {_short(payload.get('title', ''), 120)}[/]")
        dm._print(f"    file: {_short(payload.get('file_path', ''), 160)}")
    else:
        dm._print(f"  [{color}]┊ 📄 [{color}]{name}[/] ingested arXiv PDF: {_short(payload.get('title', ''), 120)}[/]")


@_action("search_source_already_ingested")
def _action_search_source_already_ingested(event: Event, dm: DisplayManager) -> None:
    payload = event.payload or {}
    agent_id = event.agent_id or "system"
    color = _agent_color(agent_id)
    name = _agent_name(agent_id)
    key = _source_progress_key(agent_id, payload)
    dm.sources.finish(key)
    dm._print(f"  [{color}]┊ ♻️  [{color}]{name}[/] reused arXiv paper: {_short(payload.get('title', ''), 120)} ({payload.get('arxiv_id', '')})[/]")


@_action("intra_cluster_review_started")
def _action_intra_cluster_review_started(event: Event, dm: DisplayManager) -> None:
    _render_intra_cluster_review_started(event, dm)


@_action("intra_cluster_review_progress")
def _action_intra_cluster_review_progress(event: Event, dm: DisplayManager) -> None:
    _render_intra_cluster_review_progress(event, dm)


@_action("intra_cluster_review_completed")
def _action_intra_cluster_review_completed(event: Event, dm: DisplayManager) -> None:
    _render_intra_cluster_review_completed(event, dm)


@_action("inter_cluster_debate_started")
def _action_inter_cluster_debate_started(event: Event, dm: DisplayManager) -> None:
    _render_inter_cluster_debate_started(event, dm)


@_action("inter_cluster_debate_progress")
def _action_inter_cluster_debate_progress(event: Event, dm: DisplayManager) -> None:
    _render_inter_cluster_debate_progress(event, dm)


@_action("inter_cluster_debate_completed")
def _action_inter_cluster_debate_completed(event, dm: DisplayManager) -> None:
    _render_inter_cluster_debate_completed(event, dm)


@_action("counter_responses_started")
def _action_counter_responses_started(event: Event, dm: DisplayManager) -> None:
    _render_counter_responses_started(event, dm)


@_action("counter_response_progress")
def _action_counter_response_progress(event: Event, dm: DisplayManager) -> None:
    _render_counter_response_progress(event, dm)


@_action("counter_responses_completed")
def _action_counter_responses_completed(event: Event, dm: DisplayManager) -> None:
    _render_counter_responses_completed(event, dm)


@_action("adjudication_started")
def _action_adjudication_started(event: Event, dm: DisplayManager) -> None:
    _render_adjudication_started(event, dm)


@_action("adjudicating_hypothesis")
def _action_adjudicating_hypothesis(event: Event, dm: DisplayManager) -> None:
    _render_adjudicating_hypothesis(event, dm)


@_action("adjudication_progress")
def _action_adjudication_progress(event: Event, dm: DisplayManager) -> None:
    _render_adjudication_progress(event, dm)


@_action("adjudication_completed")
def _action_adjudication_completed(event: Event, dm: DisplayManager) -> None:
    _render_adjudication_completed(event, dm)


# ── Catch-all Renderer ─────────────────────────────────────────────────────


def _render_unknown(event: Event, dm: DisplayManager) -> None:
    color = EVENT_COLORS.get(event.event_type, "white")
    agent_id = event.agent_id or "system"
    payload = event.payload or {}
    icon = EVENT_ICONS.get(event.event_type, "•")
    name = _agent_name(agent_id)
    detail = _kv(payload, list(payload.keys())[:5])
    dm._print(f"  [{color}]┊[/] {icon} [{color}]{name}[/] {event.event_type.value}: {detail}")


# ── Public API ──────────────────────────────────────────────────────────────

_display = DisplayManager()


def display_event(event: Event) -> None:
    _display.handle_event(event)


def start_display() -> None:
    global _research_start
    _research_start = time.monotonic()
    _display.start()


def stop_display() -> None:
    _display.stop()


def display_hypotheses(hypotheses: list[dict]) -> None:
    table = Table(title="Hypotheses")
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Status", style="bold")
    table.add_column("Confidence", justify="right")
    table.add_column("By", style="cyan")
    table.add_column("Text", max_width=60)

    for hypothesis in hypotheses:
        status_color = {
            "active": "green",
            "refuted": "red",
            "superseded": "yellow",
        }.get(hypothesis.get("status", ""), "white")

        table.add_row(
            hypothesis.get("id", "")[:12],
            f"[{status_color}]{hypothesis.get('status', '?')}[/]",
            f"{hypothesis.get('confidence', 0):.0%}",
            hypothesis.get("created_by", "?"),
            hypothesis.get("text", "")[:60],
        )

    console.print(table)


def display_graph_summary(graph_data: dict) -> None:
    nodes = graph_data.get("nodes", [])
    edges = graph_data.get("edges", [])

    label_counts: dict[str, int] = {}
    for node in nodes:
        for label in node.get("labels", []):
            label_counts[label] = label_counts.get(label, 0) + 1

    table = Table(title="Knowledge Graph")
    table.add_column("Node Type")
    table.add_column("Count", justify="right")

    for label, count in sorted(label_counts.items()):
        table.add_row(label, str(count))

    table.add_row("", "")
    table.add_row("[bold]Total Nodes[/]", f"[bold]{len(nodes)}[/]")
    table.add_row("[bold]Total Edges[/]", f"[bold]{len(edges)}[/]")

    console.print(table)


def display_report(report: str) -> None:
    console.print(
        Panel(
            report,
            title="Research Synthesis Report",
            border_style="green",
            expand=True,
        )
    )