"""
Claim models — Assumption, Hypothesis, and Finding.

These represent the intellectual progression of research:
  Assumption → Hypothesis → Finding

Assumptions are premises an agent makes explicit (often unstated in
sources). Hypotheses are testable explanations built on assumptions
and evidence. Findings are conclusions drawn from experiments or
deep analysis.
"""

from typing import Literal

from pydantic import Field

from src.models.base import BaseArtifact


class Assumption(BaseArtifact):
    """
    An explicit premise underlying an agent's reasoning.

    Good research makes assumptions visible. Agents declare these so
    other agents can challenge them. An assumption with low confidence
    is a target for investigation.
    """

    text: str = Field(
        ...,
        description="The assumption stated clearly.",
    )
    basis: str = Field(
        default="",
        description="Why the agent assumes this — what evidence or intuition supports it.",
    )
    strength: Literal["strong", "moderate", "weak"] = Field(
        default="moderate",
        description="How well-supported this assumption is.",
    )
    embedding_id: str = Field(
        default="",
        description="ID in the pgvector embeddings table.",
    )


class Hypothesis(BaseArtifact):
    """
    A proposed explanation or claim about the research question.

    Hypotheses are the core unit of intellectual progress. They can be
    tested via experiments, supported or contradicted by evidence, and
    refined through debate.
    """

    text: str = Field(
        ...,
        description="The hypothesis stated clearly and precisely.",
    )
    supporting_evidence: list[str] = Field(
        default_factory=list,
        description="IDs of artifacts (Notes, Findings, etc.) that support this hypothesis.",
    )
    against_evidence: list[str] = Field(
        default_factory=list,
        description="IDs of artifacts that contradict or weaken this hypothesis.",
    )
    testable: bool = Field(
        default=True,
        description="Whether this hypothesis can be tested via a sandboxed experiment.",
    )
    adjudication_status: str = Field(
        default="pending",
        description="Adjudication ruling: pending, upheld, revised, tabled, rejected. "
        "Set by the debate adjudicator after evidence review.",
    )
    embedding_id: str = Field(
        default="",
        description="ID in the pgvector embeddings table.",
    )


ConclusionType = Literal["supports", "refutes", "inconclusive", "partial"]


class Finding(BaseArtifact):
    """
    A conclusion drawn from an experiment result or deep analysis.

    Findings close the loop: they update the status and confidence
    of the hypothesis they evaluate, and become evidence for
    subsequent reasoning.
    """

    text: str = Field(
        ...,
        description="The finding stated clearly.",
    )
    hypothesis_id: str = Field(
        ...,
        description="ID of the Hypothesis this finding evaluates.",
    )
    experiment_id: str = Field(
        default="",
        description="ID of the Experiment that produced this finding (if any).",
    )
    conclusion_type: ConclusionType = Field(
        default="inconclusive",
        description="Whether this finding supports, refutes, or is inconclusive about the hypothesis.",
    )
    embedding_id: str = Field(
        default="",
        description="ID in the pgvector embeddings table.",
    )
