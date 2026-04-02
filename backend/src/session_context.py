"""
Per-task session context for the institute runtime.

The CLI and the HTTP API both execute the same engine code. To keep
artifacts, edges, embeddings, and emitted events scoped to the correct
session without threading session_id through every call site, the runtime
stores the current session ID in a ContextVar.
"""

from __future__ import annotations

from contextvars import ContextVar, Token


_CURRENT_SESSION_ID: ContextVar[str] = ContextVar("current_session_id", default="")


def get_current_session_id() -> str:
    """Return the current session ID for this async task, if any."""
    return _CURRENT_SESSION_ID.get()


def set_current_session_id(session_id: str) -> Token[str]:
    """Bind a session ID to the current async task and return the token."""
    return _CURRENT_SESSION_ID.set(session_id)


def reset_current_session_id(token: Token[str]) -> None:
    """Restore the previous session binding for the current async task."""
    _CURRENT_SESSION_ID.reset(token)
