"""
Reputation tracking — per-agent performance metrics within a session.

Tracks how well each agent's contributions hold up: are their hypotheses
upheld or refuted? Do their experiments pass? Are they producing output
or going silent? This data feeds into the controller's pause/reallocate
decisions and cluster debate routing (high-reputation agents become
cluster representatives).

This is NOT a trust system — it doesn't persist across sessions or
affect safety/permissions. It's a within-session quality signal.
"""

from typing import Any

from src.config import Settings, settings as default_settings
from src.graph.queries import GraphQueries


class AgentMetrics:
    """
    Performance snapshot for a single agent.

    Attributes:
        agent_id: The agent being measured.
        hypotheses_active: Hypotheses still standing.
        hypotheses_refuted: Hypotheses disproven by evidence.
        hypotheses_upheld: Hypotheses confirmed by adjudication.
        findings_count: Total findings produced.
        experiments_passed: Experiments with exit_code 0.
        experiments_failed: Experiments that failed or timed out.
        notes_count: Total notes produced.
        relations_count: Total relations created.
        consecutive_empty: Iterations with 0 output.
        composite_score: Overall performance (0.0–1.0).
    """

    def __init__(
        self,
        agent_id: str,
        hypotheses_active: int = 0,
        hypotheses_refuted: int = 0,
        hypotheses_upheld: int = 0,
        findings_count: int = 0,
        experiments_passed: int = 0,
        experiments_failed: int = 0,
        notes_count: int = 0,
        relations_count: int = 0,
        consecutive_empty: int = 0,
        config: Settings | None = None,
    ) -> None:
        self.agent_id = agent_id
        self.hypotheses_active = hypotheses_active
        self.hypotheses_refuted = hypotheses_refuted
        self.hypotheses_upheld = hypotheses_upheld
        self.findings_count = findings_count
        self.experiments_passed = experiments_passed
        self.experiments_failed = experiments_failed
        self.notes_count = notes_count
        self.relations_count = relations_count
        self.consecutive_empty = consecutive_empty
        self._config = config or default_settings

    @property
    def composite_score(self) -> float:
        """
        Compute a 0.0–1.0 composite performance score.

        Rewards:
        - Hypotheses that survive review (+0.2 each)
        - Upheld hypotheses (+0.3 each)
        - Passed experiments (+0.15 each)
        - Active contribution (notes, findings, relations)

        Penalizes:
        - Refuted hypotheses (-0.15 each)
        - Failed experiments (-0.05 each)
        - Consecutive empty iterations (-0.1 each)

        Clamped to [0.0, 1.0].
        """
        cfg = self._config
        score = cfg.reputation_baseline

        # Hypothesis quality
        total_hyp = (
            self.hypotheses_active
            + self.hypotheses_refuted
            + self.hypotheses_upheld
        )
        if total_hyp > 0:
            success_rate = (
                (self.hypotheses_active + self.hypotheses_upheld)
                / total_hyp
            )
            score += (success_rate - 0.5) * cfg.reputation_hypothesis_weight

        score += self.hypotheses_upheld * cfg.reputation_upheld_bonus

        # Experiment quality
        total_exp = self.experiments_passed + self.experiments_failed
        if total_exp > 0:
            exp_rate = self.experiments_passed / total_exp
            score += (exp_rate - 0.5) * cfg.reputation_experiment_weight

        # Productivity
        productivity = (
            self.notes_count + self.findings_count + self.relations_count
        )
        score += min(
            cfg.reputation_productivity_cap,
            productivity * cfg.reputation_productivity_per_item,
        )

        # Penalty for silence
        score -= self.consecutive_empty * cfg.reputation_empty_penalty

        return max(0.0, min(1.0, score))

    def to_dict(self) -> dict[str, Any]:
        """Serialize for prompt injection or logging."""
        return {
            "agent_id": self.agent_id,
            "hypotheses_active": self.hypotheses_active,
            "hypotheses_refuted": self.hypotheses_refuted,
            "hypotheses_upheld": self.hypotheses_upheld,
            "findings_count": self.findings_count,
            "experiments_passed": self.experiments_passed,
            "experiments_failed": self.experiments_failed,
            "notes_count": self.notes_count,
            "relations_count": self.relations_count,
            "consecutive_empty": self.consecutive_empty,
            "composite_score": round(self.composite_score, 3),
        }


class ReputationTracker:
    """
    Computes and caches per-agent performance metrics.

    Called by the controller at each iteration to decide which agents
    to pause, which to promote as cluster representatives, and how
    to reallocate budget.

    Usage:
        tracker = ReputationTracker(queries)
        metrics = await tracker.compute(agent_id)
        should_stop = await tracker.should_pause(agent_id, consecutive_empty=3)
        ranking = await tracker.rank_agents(agent_ids)
    """

    def __init__(
        self, queries: GraphQueries, config: Settings | None = None
    ) -> None:
        self._queries = queries
        self._config = config or default_settings

    async def compute(
        self, agent_id: str, consecutive_empty: int = 0
    ) -> AgentMetrics:
        """
        Compute current performance metrics for one agent.

        Queries the graph for artifact counts by type and status,
        then wraps them in an AgentMetrics object with a composite
        score.

        Args:
            agent_id: Agent to evaluate.
            consecutive_empty: Number of consecutive iterations with
                              0 output (tracked in AgentInfo state).

        Returns:
            AgentMetrics with all counts and composite score.
        """
        raw = await self._queries.get_agent_metrics(agent_id)

        return AgentMetrics(
            agent_id=agent_id,
            hypotheses_active=raw.get("hypotheses_active", 0),
            hypotheses_refuted=raw.get("hypotheses_refuted", 0),
            hypotheses_upheld=raw.get("hypotheses_upheld", 0),
            findings_count=raw.get("findings_count", 0),
            experiments_passed=raw.get("experiments_count", 0),
            experiments_failed=0,  # TODO: separate passed/failed when experiment status tracking improves
            notes_count=raw.get("notes_count", 0),
            relations_count=raw.get("relations_count", 0),
            consecutive_empty=consecutive_empty,
            config=self._config,
        )

    def should_pause(
        self, metrics: AgentMetrics, threshold: int = 3
    ) -> bool:
        """
        Determine if an agent should be paused for underperformance.

        An agent is paused if:
        - It has produced 0 output for `threshold` consecutive iterations, OR
        - Its composite score is below 0.15 (extremely poor quality)

        Args:
            metrics: The agent's current performance metrics.
            threshold: Consecutive empty iterations before pausing.

        Returns:
            True if the agent should be paused.
        """
        if metrics.consecutive_empty >= threshold:
            return True
        if metrics.composite_score < self._config.agent_pause_score_threshold:
            return True
        return False

    async def rank_agents(
        self,
        agent_ids: list[str],
        consecutive_empty_map: dict[str, int] | None = None,
    ) -> list[tuple[str, float]]:
        """
        Rank agents by composite score, highest first.

        Used to select cluster representatives for inter-cluster
        debate (top-ranked agent in each cluster).

        Args:
            agent_ids: Agents to rank.
            consecutive_empty_map: Optional map of agent_id → consecutive
                                  empty iteration count.

        Returns:
            List of (agent_id, composite_score) tuples, sorted descending.
        """
        empty_map = consecutive_empty_map or {}

        scored = []
        for aid in agent_ids:
            metrics = await self.compute(
                aid, consecutive_empty=empty_map.get(aid, 0)
            )
            scored.append((aid, metrics.composite_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    async def get_all_metrics(
        self,
        agent_ids: list[str],
        consecutive_empty_map: dict[str, int] | None = None,
    ) -> list[AgentMetrics]:
        """
        Compute metrics for all agents. Used by the controller for
        the per-agent performance summary in its evaluation prompt.
        """
        empty_map = consecutive_empty_map or {}
        return [
            await self.compute(aid, empty_map.get(aid, 0))
            for aid in agent_ids
        ]
