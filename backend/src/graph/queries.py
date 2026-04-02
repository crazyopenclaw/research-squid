"""
Complex graph traversal queries for the knowledge graph.

These go beyond simple CRUD — they answer questions like "what
contradicts this hypothesis?", "what's the provenance chain for
this finding?", and "which subproblems lack coverage?"

All queries return plain dicts/lists so they're easy to serialize
and pass to LLM prompts.
"""

from typing import Any

from src.graph.connection import Neo4jConnection


class GraphQueries:
    """
    Pre-built Cypher queries for common research graph traversals.

    These power the agents' ability to understand the current state
    of the knowledge graph and find relevant prior work.
    """

    def __init__(self, connection: Neo4jConnection) -> None:
        self._conn = connection

    # ── Hypothesis queries ───────────────────────────────────────────

    async def get_hypothesis_context(
        self, hypothesis_id: str
    ) -> dict[str, Any]:
        """
        Get a hypothesis with all its supporting and contradicting evidence.

        Returns a rich context dict suitable for inclusion in an LLM prompt.
        """
        query = """
        MATCH (h:Hypothesis {id: $id})
        OPTIONAL MATCH (h)<-[:SUPPORTS]-(supporter)
        OPTIONAL MATCH (h)<-[:CONTRADICTS]-(contradictor)
        OPTIONAL MATCH (h)-[:TESTED_BY]->(e:Experiment)-[:PRODUCED]->(r:ExperimentResult)
        OPTIONAL MATCH (h)<-[:UPDATES]-(f:Finding)
        RETURN h,
               collect(DISTINCT supporter) AS supporters,
               collect(DISTINCT contradictor) AS contradictors,
               collect(DISTINCT {experiment: e, result: r}) AS experiments,
               collect(DISTINCT f) AS findings
        """
        async with self._conn.session() as session:
            result = await session.run(query, id=hypothesis_id)
            record = await result.single()
            if not record:
                return {}

            return {
                "hypothesis": dict(record["h"]),
                "supporters": [dict(s) for s in record["supporters"] if s],
                "contradictors": [dict(c) for c in record["contradictors"] if c],
                "experiments": [
                    {
                        "experiment": dict(e["experiment"]) if e["experiment"] else None,
                        "result": dict(e["result"]) if e["result"] else None,
                    }
                    for e in record["experiments"]
                    if e.get("experiment")
                ],
                "findings": [dict(f) for f in record["findings"] if f],
            }

    async def get_contradictions(self) -> list[dict[str, Any]]:
        """
        Find all pairs of artifacts that contradict each other.

        Returns pairs with the Relation node that asserts the contradiction,
        useful for generating debate topics.
        """
        return await self.get_session_contradictions()

    async def get_session_contradictions(
        self,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Find contradiction pairs, optionally scoped to a session."""
        where_clause = ""
        params: dict[str, Any] = {}
        if session_id:
            where_clause = "WHERE coalesce(r.session_id, a.session_id, b.session_id) = $session_id"
            params["session_id"] = session_id

        query = f"""
        MATCH (a)-[r:CONTRADICTS]->(b)
        {where_clause}
        RETURN a.id AS source_id, a.text AS source_text,
               b.id AS target_id, b.text AS target_text,
               r.relation_id AS relation_id,
               r.weight AS weight
        ORDER BY r.weight DESC
        """
        async with self._conn.session() as session:
            result = await session.run(query, **params)
            return await result.data()

    async def get_all_hypotheses(
        self,
        status: str = "active",
        created_by: str | None = None,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch all hypotheses, optionally filtered by status and creator."""
        conditions = ["h.status = $status"]
        params: dict[str, Any] = {"status": status}

        if created_by:
            conditions.append("h.created_by = $created_by")
            params["created_by"] = created_by
        if session_id:
            conditions.append("h.session_id = $session_id")
            params["session_id"] = session_id

        where = "WHERE " + " AND ".join(conditions)
        query = f"""
        MATCH (h:Hypothesis)
        {where}
        RETURN h
        ORDER BY h.confidence DESC
        """
        async with self._conn.session() as session:
            result = await session.run(query, **params)
            records = await result.data()
            return [dict(r["h"]) for r in records]

    # ── Provenance tracing ───────────────────────────────────────────

    async def get_provenance_chain(
        self, artifact_id: str, max_depth: int = 10
    ) -> list[dict[str, Any]]:
        """
        Trace the full provenance of an artifact back to its sources.

        Follows DERIVED_FROM, INFORMED, and GROUNDS edges to build
        a chain from the artifact back to raw source chunks.
        """
        query = """
        MATCH path = (start {id: $id})-[:DERIVED_FROM|INFORMED|GROUNDS*1..$depth]->(ancestor)
        RETURN [node IN nodes(path) | {id: node.id, labels: labels(node), text: node.text}] AS chain
        ORDER BY length(path) DESC
        LIMIT 1
        """
        async with self._conn.session() as session:
            result = await session.run(
                query, id=artifact_id, depth=max_depth
            )
            record = await result.single()
            return record["chain"] if record else []

    # ── Coverage analysis ────────────────────────────────────────────

    async def get_coverage_stats(self, session_id: str | None = None) -> dict[str, Any]:
        """
        Compute coverage statistics across the knowledge graph.

        Returns counts of each artifact type, active vs refuted,
        and the number of unresolved contradictions.
        """
        where_clause = ""
        params: dict[str, Any] = {}
        if session_id:
            where_clause = "AND n.session_id = $session_id"
            params["session_id"] = session_id

        query = f"""
        MATCH (n)
        WHERE any(label IN labels(n) WHERE label IN
            ['Source', 'SourceChunk', 'Note', 'Assumption',
             'Hypothesis', 'Finding', 'Experiment', 'ExperimentResult']) {where_clause}
        WITH labels(n)[0] AS label, n.status AS status, count(*) AS cnt
        RETURN label, status, cnt
        ORDER BY label, status
        """
        async with self._conn.session() as session:
            result = await session.run(query, **params)
            records = await result.data()

        stats: dict[str, dict[str, int]] = {}
        for r in records:
            label = r["label"]
            status = r["status"] or "active"
            if label not in stats:
                stats[label] = {}
            stats[label][status] = r["cnt"]

        # Count unresolved contradictions
        contradictions = await self.get_session_contradictions(session_id=session_id)
        stats["_contradictions"] = {"count": len(contradictions)}

        return stats

    # ── Neighbor discovery ───────────────────────────────────────────

    async def get_neighbors(
        self,
        artifact_id: str,
        direction: str = "both",
        edge_types: list[str] | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Get all artifacts connected to a given node.

        Args:
            artifact_id: The center node.
            direction: "in", "out", or "both".
            edge_types: Optional filter on relationship types.
            limit: Max neighbors to return.
        """
        if direction == "out":
            pattern = "(a)-[r]->(b)"
        elif direction == "in":
            pattern = "(a)<-[r]-(b)"
        else:
            pattern = "(a)-[r]-(b)"

        type_filter = ""
        if edge_types:
            type_filter = "AND type(r) IN $edge_types"

        query = f"""
        MATCH {pattern}
        WHERE a.id = $id {type_filter}
        RETURN b.id AS neighbor_id, labels(b) AS labels,
               b.text AS text, type(r) AS edge_type,
               b.status AS status, b.confidence AS confidence
        LIMIT $limit
        """
        params: dict[str, Any] = {"id": artifact_id, "limit": limit}
        if edge_types:
            params["edge_types"] = edge_types

        async with self._conn.session() as session:
            result = await session.run(query, **params)
            return await result.data()

    # ── Agent workspace ──────────────────────────────────────────────

    async def get_agent_work(
        self,
        agent_id: str,
        session_id: str | None = None,
    ) -> dict[str, list[dict]]:
        """
        Get all artifacts created by a specific agent, grouped by type.

        Useful for building an agent's "portfolio" view or for
        other agents to review a specific agent's contributions.
        """
        where_clause = ""
        params: dict[str, Any] = {"agent_id": agent_id}
        if session_id:
            where_clause = "AND n.session_id = $session_id"
            params["session_id"] = session_id

        query = f"""
        MATCH (n {{created_by: $agent_id}})
        WHERE 1=1 {where_clause}
        RETURN labels(n)[0] AS label, collect(n) AS artifacts
        """
        async with self._conn.session() as session:
            result = await session.run(query, **params)
            records = await result.data()

        work: dict[str, list[dict]] = {}
        for r in records:
            work[r["label"]] = [dict(a) for a in r["artifacts"]]
        return work

    # ── Agent-level queries (for belief clustering + reputation) ────

    async def get_agent_relations(
        self,
        agent_id: str,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get all Relation nodes created by a specific agent.

        Used by the belief clusterer to determine an agent's explicit
        stances on other artifacts (supports, contradicts, etc.).
        """
        where_clause = ""
        params: dict[str, Any] = {"agent_id": agent_id}
        if session_id:
            where_clause = "AND r.session_id = $session_id"
            params["session_id"] = session_id

        query = f"""
        MATCH (r:Relation {{created_by: $agent_id}})
        WHERE 1=1 {where_clause}
        RETURN r.source_artifact_id AS source_artifact_id,
               r.target_artifact_id AS target_artifact_id,
               r.relation_type AS relation_type,
               r.weight AS weight,
               r.reasoning AS reasoning
        """
        async with self._conn.session() as session:
            result = await session.run(query, **params)
            return await result.data()

    async def get_agent_findings(
        self,
        agent_id: str,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get all Finding nodes created by a specific agent.

        Used by clustering (belief vector from conclusions) and
        reputation tracking (hypothesis outcomes).
        """
        where_clause = ""
        params: dict[str, Any] = {"agent_id": agent_id}
        if session_id:
            where_clause = "AND f.session_id = $session_id"
            params["session_id"] = session_id

        query = f"""
        MATCH (f:Finding {{created_by: $agent_id}})
        WHERE 1=1 {where_clause}
        RETURN f.id AS id, f.text AS text,
               f.hypothesis_id AS hypothesis_id,
               f.conclusion_type AS conclusion_type,
               f.confidence AS confidence
        """
        async with self._conn.session() as session:
            result = await session.run(query, **params)
            return await result.data()

    async def get_agent_hypotheses(
        self,
        agent_id: str,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get all hypotheses created by a specific agent.

        Used by clustering (authorship = strong positive stance)
        and reputation (track outcomes of agent's hypotheses).
        """
        where_clause = ""
        params: dict[str, Any] = {"agent_id": agent_id}
        if session_id:
            where_clause = "AND h.session_id = $session_id"
            params["session_id"] = session_id

        query = f"""
        MATCH (h:Hypothesis {{created_by: $agent_id}})
        WHERE 1=1 {where_clause}
        RETURN h.id AS id, h.text AS text,
               h.confidence AS confidence, h.status AS status
        """
        async with self._conn.session() as session:
            result = await session.run(query, **params)
            return await result.data()

    async def get_agent_metrics(
        self,
        agent_id: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Compute performance metrics for a single agent.

        Returns counts of hypotheses by status, findings, experiments,
        and relations. Used by the reputation tracker and controller.
        """
        where_clause = ""
        params: dict[str, Any] = {"agent_id": agent_id}
        if session_id:
            where_clause = "AND n.session_id = $session_id"
            params["session_id"] = session_id

        query = f"""
        MATCH (n {{created_by: $agent_id}})
        WHERE 1=1 {where_clause}
        WITH labels(n)[0] AS label, n.status AS status, count(*) AS cnt
        RETURN label, status, cnt
        """
        async with self._conn.session() as session:
            result = await session.run(query, **params)
            records = await result.data()

        metrics: dict[str, Any] = {
            "hypotheses_active": 0,
            "hypotheses_refuted": 0,
            "hypotheses_upheld": 0,
            "findings_count": 0,
            "experiments_count": 0,
            "relations_count": 0,
            "notes_count": 0,
        }
        for r in records:
            label = r.get("label", "")
            status = r.get("status", "active")
            cnt = r.get("cnt", 0)

            if label == "Hypothesis":
                if status == "active":
                    metrics["hypotheses_active"] += cnt
                elif status == "refuted":
                    metrics["hypotheses_refuted"] += cnt
                elif status == "upheld":
                    metrics["hypotheses_upheld"] += cnt
            elif label == "Finding":
                metrics["findings_count"] += cnt
            elif label == "Experiment":
                metrics["experiments_count"] += cnt
            elif label == "Relation":
                metrics["relations_count"] += cnt
            elif label == "Note":
                metrics["notes_count"] += cnt

        return metrics

    # ── Graph export ─────────────────────────────────────────────────

    async def export_graph(self) -> dict[str, Any]:
        """
        Export the entire knowledge graph as nodes + edges.

        Returns a structure suitable for NetworkX import or
        JSON serialization for a canvas-based viewer.
        """
        nodes_query = """
        MATCH (n)
        WHERE any(label IN labels(n) WHERE label IN
            ['Source', 'SourceChunk', 'Note', 'Assumption',
             'Hypothesis', 'Finding', 'Relation', 'Experiment',
             'ExperimentResult', 'Message'])
        RETURN n.id AS id, labels(n) AS labels,
               n.text AS text, n.status AS status,
               n.confidence AS confidence, n.created_by AS created_by
        """
        edges_query = """
        MATCH (a)-[r]->(b)
        WHERE any(label IN labels(a) WHERE label IN
            ['Source', 'SourceChunk', 'Note', 'Assumption',
             'Hypothesis', 'Finding', 'Relation', 'Experiment',
             'ExperimentResult', 'Message'])
        RETURN a.id AS source, b.id AS target, type(r) AS edge_type
        """
        async with self._conn.session() as session:
            nodes_result = await session.run(nodes_query)
            nodes = await nodes_result.data()

            edges_result = await session.run(edges_query)
            edges = await edges_result.data()

        return {"nodes": nodes, "edges": edges}

    async def get_session_top_hypotheses(
        self,
        session_id: str,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        """Return the strongest active hypotheses for one session."""
        query = """
        MATCH (h:Hypothesis {session_id: $session_id})
        WHERE h.status = 'active'
        RETURN h.id AS id,
               h.text AS text,
               h.confidence AS confidence,
               h.created_by AS created_by,
               h.adjudication_status AS adjudication_status
        ORDER BY h.confidence DESC, h.created_at DESC
        LIMIT $limit
        """
        async with self._conn.session() as session:
            result = await session.run(query, session_id=session_id, limit=limit)
            return await result.data()

    async def get_session_experiment_counts(self, session_id: str) -> dict[str, int]:
        """Count experiments by status for one session."""
        query = """
        MATCH (e:Experiment {session_id: $session_id})
        RETURN e.status AS status, count(*) AS cnt
        """
        counts = {
            "total": 0,
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "timeout": 0,
        }
        async with self._conn.session() as session:
            result = await session.run(query, session_id=session_id)
            records = await result.data()
        for record in records:
            status = (record.get("status") or "pending").lower()
            cnt = int(record.get("cnt") or 0)
            counts["total"] += cnt
            if status in counts:
                counts[status] += cnt
        return counts

    async def get_session_agent_edges(self, session_id: str) -> list[dict[str, Any]]:
        """Aggregate artifact relations into agent-to-agent graph edges."""
        query = """
        MATCH (rel:Relation {session_id: $session_id})-[:FROM_ARTIFACT]->(src)
        MATCH (rel)-[:TO_ARTIFACT]->(dst)
        WHERE rel.relation_type IN ['supports', 'contradicts', 'extends', 'refutes']
          AND coalesce(src.created_by, '') <> ''
          AND coalesce(dst.created_by, '') <> ''
        RETURN src.created_by AS source_agent_id,
               dst.created_by AS target_agent_id,
               toUpper(rel.relation_type) AS relation_type,
               count(*) AS count,
               avg(coalesce(rel.weight, 0.0)) AS weight,
               collect(DISTINCT src.text)[0..3] AS sample_claims
        ORDER BY count DESC, weight DESC
        """
        async with self._conn.session() as session:
            result = await session.run(query, session_id=session_id)
            return await result.data()

    async def get_agent_relation_summary(
        self,
        session_id: str,
        agent_id: str,
    ) -> list[dict[str, Any]]:
        """Summarize incoming and outgoing agent relations for one agent."""
        query = """
        MATCH (rel:Relation {session_id: $session_id})-[:FROM_ARTIFACT]->(src)
        MATCH (rel)-[:TO_ARTIFACT]->(dst)
        WHERE rel.relation_type IN ['supports', 'contradicts', 'extends', 'refutes']
          AND (src.created_by = $agent_id OR dst.created_by = $agent_id)
          AND coalesce(src.created_by, '') <> ''
          AND coalesce(dst.created_by, '') <> ''
        WITH rel,
             src,
             dst,
             CASE
               WHEN src.created_by = $agent_id THEN 'outgoing'
               ELSE 'incoming'
             END AS direction,
             CASE
               WHEN src.created_by = $agent_id THEN dst.created_by
               ELSE src.created_by
             END AS other_agent_id
        RETURN direction,
               toUpper(rel.relation_type) AS relation_type,
               other_agent_id,
               count(*) AS count,
               avg(coalesce(rel.weight, 0.0)) AS weight,
               collect(DISTINCT coalesce(src.text, dst.text, ''))[0..3] AS sample_claims
        ORDER BY count DESC, weight DESC
        """
        async with self._conn.session() as session:
            result = await session.run(
                query,
                session_id=session_id,
                agent_id=agent_id,
            )
            return await result.data()

    async def search_session_text(
        self,
        session_id: str,
        query_text: str,
        limit: int = 12,
    ) -> list[dict[str, Any]]:
        """Text-search artifacts within a session for UI memory search fallback."""
        query = """
        MATCH (n)
        WHERE n.session_id = $session_id
          AND any(label IN labels(n) WHERE label IN
            ['SourceChunk', 'Note', 'Assumption', 'Hypothesis', 'Finding', 'ExperimentResult'])
          AND toLower(coalesce(n.text, n.stdout, n.stderr, '')) CONTAINS toLower($query)
        RETURN n.id AS id,
               labels(n)[0] AS kind,
               coalesce(n.text, n.stdout, n.stderr, '') AS text,
               coalesce(n.title, n.text, n.id) AS title,
               n.created_by AS created_by,
               n.confidence AS confidence
        LIMIT $limit
        """
        async with self._conn.session() as session:
            result = await session.run(
                query,
                session_id=session_id,
                query=query_text,
                limit=limit,
            )
            return await result.data()
