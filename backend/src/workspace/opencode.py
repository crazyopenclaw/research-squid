"""
OpenCode integration — long-lived serve mode.

OpenCodeServer: manages a single `opencode serve` subprocess.
OpenCodeSession: one conversation thread within a server.

We use serve mode (not one-shot `opencode -p`) so sessions maintain
full context across multiple turns. Sessions persist in OpenCode's
SQLite even after the server is restarted.
"""

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from src.config import Settings
    from src.events.bus import EventBus

# Matches "http://127.0.0.1:PORT" or "http://localhost:PORT"
_PORT_RE = re.compile(r"https?://[^:]+:(\d{4,5})")


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0
    cost_usd: float = 0.0
    turn_count: int = 0

    def add_turn(self, turn: "TokenUsage") -> None:
        self.input_tokens += turn.input_tokens
        self.output_tokens += turn.output_tokens
        self.cache_read_tokens += turn.cache_read_tokens
        self.cache_creation_tokens += turn.cache_creation_tokens
        self.cost_usd += turn.cost_usd
        self.turn_count += 1


@dataclass
class OpenCodeTurnResult:
    turn: int
    message: str
    response_text: str
    files_modified: list[str]
    usage: TokenUsage
    raw: dict


class OpenCodeServer:
    """
    Long-lived `opencode serve` process for one agent workspace.

    Started lazily on first task. Kept alive across all Squid cycles.
    Stopped only at workspace cleanup (session end).

    One server per agent workspace. Port is OS-assigned (--port 0).
    Communication is via httpx over localhost.
    """

    def __init__(
        self,
        workspace_path: Path,
        config: "Settings",
        event_bus: "EventBus",
    ) -> None:
        self._workspace = workspace_path
        self._config = config
        self._bus = event_bus
        self._proc: asyncio.subprocess.Process | None = None
        self._port: int | None = None
        self._base_url: str = ""
        self._http = httpx.AsyncClient(timeout=300.0)

    async def start(self) -> None:
        """Start `opencode serve` as a subprocess. Waits until /health responds."""
        await self._write_config()

        self._proc = await asyncio.create_subprocess_exec(
            "opencode", "serve", "--port", "0",
            cwd=str(self._workspace),
            env={**os.environ, "OPENCODE_SERVER_PASSWORD": ""},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        self._port = await self._read_port_from_stdout()
        self._base_url = f"http://127.0.0.1:{self._port}"
        await self._wait_healthy()

        from src.models.events import Event, EventType
        await self._bus.publish(Event(
            event_type=EventType.WORKSPACE_OPENCODE_SERVER_STARTED,
            payload={"workspace": str(self._workspace), "port": self._port},
        ))

    async def stop(self) -> None:
        """Gracefully stop the server: POST /dispose first, then terminate."""
        if self._proc and self._proc.returncode is None:
            try:
                await self._http.post(
                    f"{self._base_url}/dispose", timeout=5.0
                )
            except Exception:
                pass
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self._proc.kill()
        await self._http.aclose()

    async def new_session(self, title: str = "") -> "OpenCodeSession":
        """Create a new OpenCode session. Returns an OpenCodeSession handle."""
        resp = await self._http.post(
            f"{self._base_url}/session",
            json={"title": title} if title else {},
        )
        resp.raise_for_status()
        info = resp.json()
        return OpenCodeSession(
            session_id=info["id"],
            server=self,
            workspace=self._workspace,
        )

    async def resume_session(self, opencode_session_id: str) -> "OpenCodeSession":
        """Reopen an existing session by its persisted ID."""
        resp = await self._http.get(
            f"{self._base_url}/session/{opencode_session_id}"
        )
        resp.raise_for_status()
        return OpenCodeSession(
            session_id=opencode_session_id,
            server=self,
            workspace=self._workspace,
        )

    async def list_sessions(self) -> list[dict]:
        """List all sessions for this workspace directory."""
        resp = await self._http.get(
            f"{self._base_url}/session",
            params={"directory": str(self._workspace)},
        )
        resp.raise_for_status()
        return resp.json()

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.returncode is None

    @property
    def base_url(self) -> str:
        return self._base_url

    async def _write_config(self) -> None:
        """Write .opencode.json to the workspace before starting the server."""
        config: dict = {
            "autoapprove": True,
            "autoshare": False,
        }
        if self._config.workspace_opencode_model:
            config["model"] = self._config.workspace_opencode_model

        config_path = self._workspace / ".opencode.json"
        content = json.dumps(config, indent=2)
        await asyncio.to_thread(config_path.write_text, content, encoding="utf-8")

    async def _read_port_from_stdout(self) -> int:
        """Read stdout until we find the listening port URL."""
        assert self._proc is not None
        deadline = asyncio.get_event_loop().time() + 15.0

        while True:
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 0:
                raise RuntimeError(
                    "Timed out waiting for OpenCode server to print its port"
                )
            try:
                line = await asyncio.wait_for(
                    self._proc.stdout.readline(),  # type: ignore[union-attr]
                    timeout=remaining,
                )
            except asyncio.TimeoutError:
                raise RuntimeError(
                    "Timed out waiting for OpenCode server to print its port"
                )
            if not line:
                raise RuntimeError(
                    "OpenCode server exited during startup (stdout closed). "
                    "Check that `opencode` is installed and `opencode serve` works."
                )
            text = line.decode("utf-8", errors="replace")
            match = _PORT_RE.search(text)
            if match:
                return int(match.group(1))

    async def _wait_healthy(self) -> None:
        """Poll /health until the server responds 200 or timeout."""
        for _ in range(30):
            try:
                resp = await self._http.get(
                    f"{self._base_url}/health", timeout=1.0
                )
                if resp.status_code == 200:
                    return
            except Exception:
                pass
            await asyncio.sleep(0.5)
        raise RuntimeError(
            f"OpenCode server at {self._base_url} did not become healthy"
        )


class OpenCodeSession:
    """
    One conversation thread within a running OpenCode server.

    Context is maintained across ALL send() calls — OpenCode remembers
    what it wrote, what ran, what failed, across every turn.

    Sessions persist in OpenCode's SQLite even after server restarts.
    Resume via OpenCodeServer.resume_session(session_id).
    """

    def __init__(
        self,
        session_id: str,
        server: OpenCodeServer,
        workspace: Path,
    ) -> None:
        self.session_id = session_id
        self._server = server
        self._workspace = workspace
        self._turn_count = 0
        self._accumulated_usage = TokenUsage()

    async def send(
        self, message: str, timeout: int | None = None
    ) -> OpenCodeTurnResult:
        """
        Send a message to OpenCode and wait for its full response.

        OpenCode autonomously uses its tools (read, write, bash, grep)
        to complete the task, then returns a summary.

        Token usage is extracted directly from info.usage in the response.
        """
        self._turn_count += 1
        before_files = set(self._list_workspace_files())

        payload = {"parts": [{"type": "text", "content": message}]}
        effective_timeout = timeout or self._server._config.workspace_opencode_timeout

        resp = await self._server._http.post(
            f"{self._server.base_url}/session/{self.session_id}/message",
            json=payload,
            timeout=httpx.Timeout(effective_timeout),
        )
        resp.raise_for_status()
        data = resp.json()

        # Extract token usage directly from response — no proxy needed
        info = data.get("info", {})
        usage_raw = info.get("usage", {})
        turn_usage = TokenUsage(
            input_tokens=usage_raw.get("inputTokens", 0),
            output_tokens=usage_raw.get("outputTokens", 0),
            cache_read_tokens=usage_raw.get("cacheReadTokens", 0),
            cache_creation_tokens=usage_raw.get("cacheCreationTokens", 0),
            cost_usd=info.get("cost", 0.0),
        )
        self._accumulated_usage.add_turn(turn_usage)

        # Extract text from response parts
        parts = data.get("parts", [])
        response_text = " ".join(
            p.get("content", "") or p.get("text", "")
            for p in parts
            if p.get("type") in ("text", "reasoning")
        )

        after_files = set(self._list_workspace_files())
        files_modified = list(after_files - before_files)

        return OpenCodeTurnResult(
            turn=self._turn_count,
            message=message,
            response_text=response_text,
            files_modified=files_modified,
            usage=turn_usage,
            raw=data,
        )

    async def fork_from(self, message_id: str) -> "OpenCodeSession":
        """
        Create a new session branching from a specific message.

        Useful for a second Squid that wants to try a variation of
        Squid 1's experiment with full context but a different direction.
        """
        resp = await self._server._http.post(
            f"{self._server.base_url}/session/{self.session_id}"
            f"/message/{message_id}/fork"
        )
        resp.raise_for_status()
        new_info = resp.json()
        return OpenCodeSession(
            session_id=new_info["id"],
            server=self._server,
            workspace=self._workspace,
        )

    async def close(self) -> None:
        """
        Soft close — does NOT delete the session from SQLite.

        Session remains resumable via server.resume_session(session_id).
        Nothing to do here — OpenCode persists automatically.
        """

    @property
    def accumulated_usage(self) -> TokenUsage:
        return self._accumulated_usage

    def _list_workspace_files(self) -> list[str]:
        """List workspace files, excluding .history/."""
        result = []
        for p in self._workspace.rglob("*"):
            if p.is_file() and ".history" not in p.parts:
                result.append(str(p.relative_to(self._workspace)))
        return result
