"""
Neo4j schema bootstrap — constraints, indexes, and initial setup.

Run once at startup or via `scripts/bootstrap_neo4j.py`. Idempotent —
safe to run multiple times (uses IF NOT EXISTS).
"""

from src.graph.connection import Neo4jConnection

# All node labels in the knowledge graph ontology
NODE_LABELS = [
    "Source",
    "SourceChunk",
    "Note",
    "Assumption",
    "Hypothesis",
    "Finding",
    "Relation",
    "Experiment",
    "ExperimentResult",
    "Message",
]

# Uniqueness constraints — every node must have a unique id
CONSTRAINTS = [
    f"CREATE CONSTRAINT {label.lower()}_id IF NOT EXISTS "
    f"FOR (n:{label}) REQUIRE n.id IS UNIQUE"
    for label in NODE_LABELS
]

# Full-text indexes for keyword search on text-heavy nodes
FULLTEXT_INDEXES = [
    "CREATE FULLTEXT INDEX note_text IF NOT EXISTS FOR (n:Note) ON EACH [n.text]",
    "CREATE FULLTEXT INDEX hypothesis_text IF NOT EXISTS FOR (n:Hypothesis) ON EACH [n.text]",
    "CREATE FULLTEXT INDEX assumption_text IF NOT EXISTS FOR (n:Assumption) ON EACH [n.text]",
    "CREATE FULLTEXT INDEX finding_text IF NOT EXISTS FOR (n:Finding) ON EACH [n.text]",
    "CREATE FULLTEXT INDEX message_text IF NOT EXISTS FOR (n:Message) ON EACH [n.text]",
]

# Regular indexes for common lookups
INDEXES = [
    "CREATE INDEX source_type_idx IF NOT EXISTS FOR (n:Source) ON (n.source_type)",
    "CREATE INDEX chunk_source_idx IF NOT EXISTS FOR (n:SourceChunk) ON (n.source_id)",
    "CREATE INDEX artifact_status_idx IF NOT EXISTS FOR (n:Hypothesis) ON (n.status)",
    "CREATE INDEX artifact_creator_idx IF NOT EXISTS FOR (n:Hypothesis) ON (n.created_by)",
    "CREATE INDEX experiment_status_idx IF NOT EXISTS FOR (n:Experiment) ON (n.status)",
    "CREATE INDEX message_to_idx IF NOT EXISTS FOR (n:Message) ON (n.to_agent)",
    "CREATE INDEX message_read_idx IF NOT EXISTS FOR (n:Message) ON (n.read)",
]


async def bootstrap_schema(conn: Neo4jConnection) -> None:
    """
    Create all constraints, indexes, and full-text indexes in Neo4j.

    Idempotent — uses IF NOT EXISTS on every statement.
    Logs each step so you can see what was created.
    """
    all_statements = CONSTRAINTS + FULLTEXT_INDEXES + INDEXES

    async with conn.session() as session:
        for statement in all_statements:
            await session.run(statement)
