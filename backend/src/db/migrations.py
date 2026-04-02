"""
PostgreSQL schema bootstrap — tables for embeddings, experiments,
sessions, and event log.

Run once at startup or via `scripts/bootstrap_postgres.py`. Idempotent —
uses IF NOT EXISTS on every statement.
"""

from sqlalchemy import text

from src.db.connection import PostgresConnection


MIGRATIONS = [
    # Enable pgvector extension
    "CREATE EXTENSION IF NOT EXISTS vector",

    # Embeddings table — used by LlamaIndex pgvector integration
    """
    CREATE TABLE IF NOT EXISTS embeddings (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        artifact_id TEXT NOT NULL,
        artifact_type TEXT NOT NULL,
        text TEXT NOT NULL,
        embedding vector(1536),
        metadata JSONB DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,

    # Indexes for the embeddings table
    "CREATE INDEX IF NOT EXISTS idx_embeddings_artifact ON embeddings(artifact_id)",
    "CREATE INDEX IF NOT EXISTS idx_embeddings_type ON embeddings(artifact_type)",

    # Experiment tracking
    """
    CREATE TABLE IF NOT EXISTS experiments (
        id TEXT PRIMARY KEY,
        hypothesis_id TEXT NOT NULL,
        spec JSONB NOT NULL,
        status TEXT DEFAULT 'pending',
        container_id TEXT,
        started_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ,
        exit_code INTEGER,
        stdout TEXT,
        stderr TEXT,
        execution_time_seconds FLOAT,
        created_by TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,

    # Research session tracking
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,
        research_question TEXT NOT NULL,
        state JSONB NOT NULL DEFAULT '{}',
        status TEXT DEFAULT 'active',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,

    # Event log — append-only, for replay and audit
    """
    CREATE TABLE IF NOT EXISTS event_log (
        id SERIAL PRIMARY KEY,
        session_id TEXT REFERENCES sessions(id),
        event_type TEXT NOT NULL,
        agent_id TEXT,
        artifact_id TEXT,
        payload JSONB NOT NULL DEFAULT '{}',
        created_at TIMESTAMPTZ DEFAULT NOW()
    )
    """,

    "CREATE INDEX IF NOT EXISTS idx_events_session ON event_log(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_events_type ON event_log(event_type)",
]


async def bootstrap_postgres(conn: PostgresConnection) -> None:
    """
    Run all migration statements to set up the Postgres schema.

    Idempotent — safe to run on every startup.
    """
    async with conn.session() as session:
        for migration in MIGRATIONS:
            await session.execute(text(migration))
