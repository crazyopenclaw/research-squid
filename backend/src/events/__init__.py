"""
Event bus — decouples the core research engine from any UI layer.

The bus supports in-process pub/sub with optional persistence to
Postgres. CLI subscribes with a Rich printer. A future web UI
would subscribe with a WebSocket broadcaster.
"""
