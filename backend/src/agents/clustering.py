"""
Belief-based clustering — groups agents by epistemic stance.

Instead of clustering by topic (which subproblem they work on),
this module clusters agents by what they actually believe: which
hypotheses they support, contradict, or have no opinion on. This
makes debate productive — agents who agree don't waste time
debating each other, while genuinely opposing clusters get paired
for inter-cluster challenges.

Clusters are recomputed every 2-3 iterations (hybrid strategy)
to balance accuracy and computational cost.
"""

import math
from typing import Any

from src.config import Settings, settings as default_settings
from src.graph.queries import GraphQueries
from src.models.agent_state import BeliefCluster


class BeliefClusterer:
    """
    Groups agents into clusters based on shared/opposing beliefs.

    The clustering process:
    1. Compute a belief vector per agent (stance on each hypothesis)
    2. Compute pairwise cosine similarity between belief vectors
    3. Hierarchical agglomerative clustering into groups
    4. Label clusters with their shared/contested hypotheses

    Usage:
        clusterer = BeliefClusterer(queries)
        clusters = await clusterer.cluster_agents(agent_ids)
        pairs = await clusterer.form_debate_pairs(clusters)
    """

    def __init__(
        self, queries: GraphQueries, config: Settings | None = None
    ) -> None:
        self._queries = queries
        self._config = config or default_settings

    async def compute_belief_vector(
        self,
        agent_id: str,
        session_id: str | None = None,
    ) -> dict[str, float]:
        """
        Compute an agent's stance on every hypothesis in the graph.

        Returns a dict mapping hypothesis_id → stance value:
        - +1.0: agent created or explicitly supports this hypothesis
        - -1.0: agent refuted or contradicts this hypothesis
        - +0.5: agent extends this hypothesis
        - -0.5: agent challenged (questioned) this hypothesis
        - 0.0: no opinion

        Built from: Relations created by this agent, Findings with
        conclusion_type, and hypothesis authorship.
        """
        # Get all active hypotheses
        all_hypotheses = await self._queries.get_all_hypotheses(
            status="active",
            session_id=session_id,
        )
        hypothesis_ids = [h["id"] for h in all_hypotheses]

        if not hypothesis_ids:
            return {}

        # Get all relations created by this agent
        relations = await self._queries.get_agent_relations(agent_id, session_id=session_id)

        # Get all findings created by this agent
        findings = await self._queries.get_agent_findings(agent_id, session_id=session_id)

        # Get hypotheses created by this agent
        created = await self._queries.get_agent_hypotheses(agent_id, session_id=session_id)
        created_ids = {h["id"] for h in created}

        # Build belief vector
        beliefs: dict[str, float] = {}
        for hid in hypothesis_ids:
            beliefs[hid] = 0.0

        # Authorship = strong positive stance
        for hid in created_ids:
            if hid in beliefs:
                beliefs[hid] = self._config.belief_authorship_weight

        # Relations encode explicit stances (weights from config)
        relation_weights = {
            "supports": self._config.belief_supports_weight,
            "extends": self._config.belief_extends_weight,
            "questions": self._config.belief_questions_weight,
            "contradicts": self._config.belief_contradicts_weight,
            "refutes": self._config.belief_refutes_weight,
            "depends_on": self._config.belief_depends_on_weight,
            "derived_from": self._config.belief_derived_from_weight,
        }
        for rel in relations:
            target = rel.get("target_artifact_id", "")
            rtype = rel.get("relation_type", "").lower()
            if target in beliefs and rtype in relation_weights:
                # Use the strongest stance (don't average to zero)
                new_val = relation_weights[rtype]
                if abs(new_val) > abs(beliefs[target]):
                    beliefs[target] = new_val

        # Findings encode investigation outcomes (weights from config)
        conclusion_weights = {
            "supports": self._config.belief_finding_supports_weight,
            "refutes": self._config.belief_finding_refutes_weight,
            "inconclusive": self._config.belief_finding_inconclusive_weight,
            "partial": self._config.belief_finding_partial_weight,
        }
        for finding in findings:
            hid = finding.get("hypothesis_id", "")
            conclusion = finding.get("conclusion_type", "").lower()
            if hid in beliefs and conclusion in conclusion_weights:
                new_val = conclusion_weights[conclusion]
                if abs(new_val) > abs(beliefs[hid]):
                    beliefs[hid] = new_val

        return beliefs

    async def cluster_agents(
        self,
        agent_ids: list[str],
        n_clusters: int | None = None,
        session_id: str | None = None,
    ) -> list[BeliefCluster]:
        """
        Cluster agents by belief similarity using agglomerative clustering.

        Uses cosine similarity on belief vectors. Agents with similar
        stances (both support the same hypotheses, both contradict the
        same ones) end up in the same cluster.

        Args:
            agent_ids: IDs of all active agents to cluster.
            n_clusters: Target number of clusters. If None, auto-selects
                       based on agent count (~sqrt(N), min 2, max 15).

        Returns:
            List of BeliefCluster dicts.
        """
        if len(agent_ids) <= 2:
            # Too few to cluster — everyone is one group
            return [BeliefCluster(
                cluster_id="cluster-0",
                agent_ids=list(agent_ids),
                shared_hypotheses=[],
                contested_hypotheses=[],
            )]

        # Compute belief vectors for all agents
        vectors: dict[str, dict[str, float]] = {}
        for aid in agent_ids:
            vectors[aid] = await self.compute_belief_vector(aid, session_id=session_id)

        # Get all hypothesis IDs (union of all vectors)
        all_hids = set()
        for v in vectors.values():
            all_hids.update(v.keys())
        hid_list = sorted(all_hids)

        if not hid_list:
            # No hypotheses yet — cluster by persona similarity
            # (fallback: put everyone in one cluster)
            return [BeliefCluster(
                cluster_id="cluster-0",
                agent_ids=list(agent_ids),
                shared_hypotheses=[],
                contested_hypotheses=[],
            )]

        # Convert to dense vectors for similarity computation
        dense: dict[str, list[float]] = {}
        for aid in agent_ids:
            v = vectors.get(aid, {})
            dense[aid] = [v.get(hid, 0.0) for hid in hid_list]

        # Auto-select cluster count
        if n_clusters is None:
            n_clusters = max(
                self._config.min_clusters,
                min(self._config.max_clusters, int(math.sqrt(len(agent_ids)))),
            )
        n_clusters = min(n_clusters, len(agent_ids))

        # Simple agglomerative clustering (no scipy dependency needed)
        clusters_map = self._agglomerative_cluster(
            agent_ids, dense, n_clusters
        )

        # Build BeliefCluster objects with metadata
        result = []
        for cid, members in clusters_map.items():
            shared, contested = self._classify_hypotheses(
                members, vectors, hid_list
            )
            result.append(BeliefCluster(
                cluster_id=f"cluster-{cid}",
                agent_ids=members,
                shared_hypotheses=shared,
                contested_hypotheses=contested,
            ))

        return result

    async def form_debate_pairs(
        self,
        clusters: list[BeliefCluster],
    ) -> list[dict[str, Any]]:
        """
        Create debate matchups BETWEEN opposing clusters.

        For each pair of clusters, find hypotheses where they disagree
        and create (challenger_agent_id, target_hypothesis_id) pairs.
        The challenger is the cluster representative (first agent).

        Returns:
            List of dicts with keys: challenger_id, target_hypothesis_id,
            source_cluster, target_cluster.
        """
        pairs: list[dict[str, Any]] = []

        for i, c1 in enumerate(clusters):
            for c2 in clusters[i + 1:]:
                # Find hypotheses that c1 supports but c2 contests (or vice versa)
                c1_supports = set(c1["shared_hypotheses"])
                c2_supports = set(c2["shared_hypotheses"])

                # c1 representative challenges c2's hypotheses
                disagreements = c2_supports - c1_supports
                if disagreements and c1["agent_ids"]:
                    challenger = c1["agent_ids"][0]  # Cluster rep
                    cap = self._config.max_debate_pairs_per_cluster
                    for hid in list(disagreements)[:cap]:
                        pairs.append({
                            "challenger_id": challenger,
                            "target_hypothesis_id": hid,
                            "source_cluster": c1["cluster_id"],
                            "target_cluster": c2["cluster_id"],
                        })

                # c2 representative challenges c1's hypotheses
                disagreements = c1_supports - c2_supports
                if disagreements and c2["agent_ids"]:
                    challenger = c2["agent_ids"][0]
                    cap = self._config.max_debate_pairs_per_cluster
                    for hid in list(disagreements)[:cap]:
                        pairs.append({
                            "challenger_id": challenger,
                            "target_hypothesis_id": hid,
                            "source_cluster": c2["cluster_id"],
                            "target_cluster": c1["cluster_id"],
                        })

        return pairs

    def _cosine_similarity(
        self, a: list[float], b: list[float]
    ) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a)) or 1e-9
        norm_b = math.sqrt(sum(x * x for x in b)) or 1e-9
        return dot / (norm_a * norm_b)

    def _agglomerative_cluster(
        self,
        agent_ids: list[str],
        dense: dict[str, list[float]],
        n_clusters: int,
    ) -> dict[int, list[str]]:
        """
        Simple agglomerative clustering by cosine similarity.

        Merges the two most similar clusters at each step until
        n_clusters remain. No external dependencies required.
        """
        # Initialize: each agent is its own cluster
        clusters: dict[int, list[str]] = {
            i: [aid] for i, aid in enumerate(agent_ids)
        }

        while len(clusters) > n_clusters:
            # Find the most similar pair of clusters
            best_sim = -2.0
            best_pair = (0, 0)

            cids = list(clusters.keys())
            for i, c1 in enumerate(cids):
                for c2 in cids[i + 1:]:
                    # Average-link similarity
                    sims = []
                    for a1 in clusters[c1]:
                        for a2 in clusters[c2]:
                            sims.append(
                                self._cosine_similarity(dense[a1], dense[a2])
                            )
                    avg_sim = sum(sims) / len(sims) if sims else 0.0

                    if avg_sim > best_sim:
                        best_sim = avg_sim
                        best_pair = (c1, c2)

            # Merge the most similar pair
            c1, c2 = best_pair
            clusters[c1].extend(clusters[c2])
            del clusters[c2]

        # Re-number clusters 0..N-1
        return {i: members for i, members in enumerate(clusters.values())}

    def _classify_hypotheses(
        self,
        members: list[str],
        vectors: dict[str, dict[str, float]],
        hid_list: list[str],
    ) -> tuple[list[str], list[str]]:
        """
        Classify hypotheses as shared or contested within a cluster.

        Shared: all members have stance > 0 (or created it).
        Contested: members disagree (some positive, some negative).
        """
        shared = []
        contested = []

        for hid in hid_list:
            stances = [vectors.get(m, {}).get(hid, 0.0) for m in members]
            non_zero = [
                s for s in stances
                if abs(s) > self._config.cluster_stance_threshold
            ]

            if not non_zero:
                continue

            # All agree (same sign)
            all_positive = all(s > 0 for s in non_zero)
            all_negative = all(s < 0 for s in non_zero)

            if all_positive:
                shared.append(hid)
            elif not all_negative:
                # Mixed — some positive, some negative
                contested.append(hid)

        return shared, contested
