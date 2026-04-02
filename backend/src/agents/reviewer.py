"""
Reviewer agent — challenges, supports, and extends hypotheses.

The Reviewer drives the debate cycle. It examines hypotheses from
all squids, evaluates evidence quality, finds weaknesses, and
pushes the research toward stronger conclusions.
"""

from typing import Any

from pydantic import BaseModel, Field

from src.config import Settings, settings as default_settings
from src.events.bus import EventBus
from src.graph.queries import GraphQueries
from src.graph.repository import GraphRepository
from src.llm.client import LLMClient
from src.llm.prompts import REVIEWER_SYSTEM, REVIEWER_CHALLENGE
from src.models.claim import Finding
from src.models.events import Event, EventType
from src.models.experiment import Experiment, ExperimentSpec
from src.models.message import Message, MessageType
from src.models.relation import Relation, RelationType


class ReviewOutput(BaseModel):
    """Structured output from a review of a hypothesis."""

    verdict: str = ""
    reasoning: str = ""
    confidence: float = Field(
        default_factory=lambda: default_settings.review_default_confidence
    )
    weaknesses: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    relations: list[dict[str, Any]] = Field(default_factory=list)
    suggested_experiments: list[dict[str, Any]] = Field(default_factory=list)
    messages: list[dict[str, Any]] = Field(default_factory=list)


class ReviewerAgent:
    """
    Critically evaluates hypotheses and drives scientific debate.

    For each hypothesis it reviews, the Reviewer:
    1. Fetches full context (supporting/contradicting evidence, experiments)
    2. Evaluates the strength of the hypothesis
    3. Identifies weaknesses and strengths
    4. Creates relations (supports/contradicts/refutes)
    5. Proposes experiments to resolve disagreements
    6. Sends messages to the hypothesis author

    Usage:
        reviewer = ReviewerAgent(llm, graph, queries, event_bus)
        results = await reviewer.review_hypothesis(hypothesis_id, agent_id)
    """

    def __init__(
        self,
        llm: LLMClient,
        graph: GraphRepository,
        queries: GraphQueries,
        event_bus: EventBus,
        config: Settings | None = None,
    ) -> None:
        self._llm = llm
        self._graph = graph
        self._queries = queries
        self._bus = event_bus
        self._config = config or default_settings

    async def review_hypothesis(
        self,
        hypothesis_id: str,
        reviewer_agent_id: str,
    ) -> dict[str, Any]:
        """
        Review a single hypothesis and produce critique artifacts.

        Args:
            hypothesis_id: ID of the hypothesis to review.
            reviewer_agent_id: ID of the reviewing agent.

        Returns:
            Dict with IDs of created findings, relations, experiments, messages.
        """
        # Fetch full hypothesis context from the graph
        context = await self._queries.get_hypothesis_context(hypothesis_id)
        if not context:
            return {}

        hypothesis = context["hypothesis"]

        # Format evidence for the prompt
        supporting = "\n".join(
            f"- {s.get('text', '')}" for s in context["supporters"]
        ) or "None"
        contradicting = "\n".join(
            f"- {c.get('text', '')}" for c in context["contradictors"]
        ) or "None"
        exp_results = "\n".join(
            f"- Experiment: {e['experiment'].get('spec_code', '')[:200]}... "
            f"Exit code: {e['result'].get('exit_code', '?')}"
            for e in context["experiments"]
            if e.get("result")
        ) or "None"

        prompt = REVIEWER_CHALLENGE.format(
            hypothesis_id=hypothesis_id,
            hypothesis_text=hypothesis.get("text", ""),
            created_by=hypothesis.get("created_by", ""),
            confidence=hypothesis.get("confidence", "?"),
            supporting_evidence=supporting,
            contradicting_evidence=contradicting,
            experiment_results=exp_results,
        )

        await self._bus.publish(Event(
            event_type=EventType.AGENT_ACTION,
            agent_id=reviewer_agent_id,
            payload={
                "action": "reviewing_hypothesis",
                "hypothesis_id": hypothesis_id,
                "hypothesis_text": hypothesis.get("text", ""),
                "created_by": hypothesis.get("created_by", ""),
            },
        ))

        output = await self._llm.complete_structured(
            prompt=prompt,
            response_model=ReviewOutput,
            system=REVIEWER_SYSTEM,
            temperature=self._config.temperature_reviewer,
        )

        # Store review artifacts
        results = await self._store_review(
            output, hypothesis_id, hypothesis, reviewer_agent_id
        )

        await self._bus.publish(Event(
            event_type=EventType.AGENT_ACTION,
            agent_id=reviewer_agent_id,
            payload={
                "action": "reviewed_hypothesis",
                "hypothesis_id": hypothesis_id,
                "hypothesis_text": hypothesis.get("text", ""),
                "verdict": output.verdict,
            },
        ))

        return results

    async def _store_review(
        self,
        output: ReviewOutput,
        hypothesis_id: str,
        hypothesis: dict,
        reviewer_agent_id: str,
    ) -> dict[str, Any]:
        """Store all artifacts produced by the review."""
        findings_created: list[str] = []
        relations_created: list[str] = []
        experiments_proposed: list[str] = []
        messages_sent: list[str] = []

        # Create a finding summarizing the review
        conclusion_map = {
            "support": "supports",
            "challenge": "inconclusive",
            "refute": "refutes",
            "extend": "partial",
        }
        finding = Finding(
            text=output.reasoning,
            hypothesis_id=hypothesis_id,
            conclusion_type=conclusion_map.get(output.verdict, output.verdict or "inconclusive"),
            created_by=reviewer_agent_id,
            confidence=output.confidence,
        )
        await self._graph.create(finding)
        await self._graph.link_finding_to_hypothesis(finding.id, hypothesis_id)
        findings_created.append(finding.id)

        # If refuted, update hypothesis status
        if (
            output.verdict == "refute"
            and output.confidence > self._config.reviewer_refutation_confidence
        ):
            await self._graph.update_status(
                hypothesis_id, "refuted", reviewer_agent_id
            )

        # Store relations
        for rel_data in output.relations:
            relation = Relation(
                source_artifact_id=(
                    rel_data.get("source_artifact_id") or finding.id
                ),
                target_artifact_id=(
                    rel_data.get("target_artifact_id") or hypothesis_id
                ),
                relation_type=RelationType.from_llm(
                    rel_data.get("relation_type", "")
                ),
                reasoning=rel_data.get("reasoning", ""),
                weight=rel_data.get(
                    "weight", self._config.relation_default_weight
                ),
                created_by=reviewer_agent_id,
            )
            await self._graph.create_relation(relation)
            relations_created.append(relation.id)

        # Propose experiments to resolve disagreements
        for exp_data in output.suggested_experiments:
            spec = ExperimentSpec(
                code=exp_data.get("code", ""),
                expected_outcome=exp_data.get("expected_outcome", ""),
            )
            experiment = Experiment(
                hypothesis_id=hypothesis_id,
                spec=spec,
                created_by=reviewer_agent_id,
            )
            await self._graph.create(experiment)
            await self._graph.link_hypothesis_to_experiment(
                hypothesis_id, experiment.id
            )
            experiments_proposed.append(experiment.id)

        # Send messages to the hypothesis author (with typed protocol)
        author_id = hypothesis.get("created_by", "")
        for msg_data in output.messages:
            to = msg_data.get("to_agent") or author_id
            if to:
                # Determine message type from verdict context
                default_type = {
                    "refute": "objection",
                    "challenge": "objection",
                    "support": "acknowledgment",
                    "extend": "evidence",
                }.get(output.verdict, "question")

                message = Message(
                    from_agent=reviewer_agent_id,
                    to_agent=to,
                    text=msg_data.get("text", ""),
                    message_type=MessageType.from_llm(
                        msg_data.get("message_type", default_type)
                    ),
                    regarding_artifact_id=hypothesis_id,
                    created_by=reviewer_agent_id,
                )
                await self._graph.create_message(message)
                messages_sent.append(message.id)

        return {
            "findings_created": findings_created,
            "relations_created": relations_created,
            "experiments_proposed": experiments_proposed,
            "messages_sent": messages_sent,
        }

    async def review_all_hypotheses(
        self,
        reviewer_agent_id: str,
        exclude_agent: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Review all active hypotheses (optionally excluding one agent's work).

        Used during the debate cycle to ensure comprehensive review.
        """
        hypotheses = await self._queries.get_all_hypotheses(status="active")
        results = []

        for h in hypotheses:
            # Skip reviewing your own hypotheses (optional)
            if exclude_agent and h.get("created_by") == exclude_agent:
                continue

            result = await self.review_hypothesis(
                h["id"], reviewer_agent_id
            )
            results.append(result)

        return results
