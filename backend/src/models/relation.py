"""
Relation model — typed, weighted edges between any two artifacts.

Relations are first-class nodes in the knowledge graph (not just Neo4j
edges). This lets agents debate the relationships themselves — e.g.,
"I disagree that Hypothesis A supports Hypothesis B."

Every Relation also creates a direct Neo4j edge for fast graph traversal.
"""

from enum import Enum

from pydantic import Field

from src.models.base import BaseArtifact


class RelationType(str, Enum):
    """The semantic type of a relationship between two artifacts."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    EXTENDS = "extends"
    REFUTES = "refutes"
    DEPENDS_ON = "depends_on"
    DERIVED_FROM = "derived_from"
    QUESTIONS = "questions"

    @classmethod
    def from_llm(cls, value: str) -> "RelationType":
        """
        Parse a relation type from LLM output, handling common synonyms.

        LLMs often return synonyms like 'challenges', 'opposes', 'confirms'.
        This maps them to the closest valid enum value rather than crashing.
        """
        value = value.strip().lower()

        # Direct match
        try:
            return cls(value)
        except ValueError:
            pass

        # Common LLM synonyms
        synonyms = {
            "challenges": cls.CONTRADICTS,
            "challenge": cls.CONTRADICTS,
            "opposes": cls.CONTRADICTS,
            "disagrees": cls.CONTRADICTS,
            "confirms": cls.SUPPORTS,
            "support": cls.SUPPORTS,
            "backs": cls.SUPPORTS,
            "agrees": cls.SUPPORTS,
            "extend": cls.EXTENDS,
            "builds_on": cls.EXTENDS,
            "elaborates": cls.EXTENDS,
            "refute": cls.REFUTES,
            "disproves": cls.REFUTES,
            "invalidates": cls.REFUTES,
            "depends": cls.DEPENDS_ON,
            "requires": cls.DEPENDS_ON,
            "derived": cls.DERIVED_FROM,
            "based_on": cls.DERIVED_FROM,
            "question": cls.QUESTIONS,
            "queries": cls.QUESTIONS,
        }
        if value in synonyms:
            return synonyms[value]

        # Fallback — default to QUESTIONS (least committal)
        return cls.QUESTIONS


class Relation(BaseArtifact):
    """
    A typed, weighted link between two artifacts.

    Relations are how agents express opinions about connections in the
    knowledge graph. They can support, contradict, extend, or refute
    existing work — making the graph a living, debated structure.
    """

    source_artifact_id: str = Field(
        ...,
        description="ID of the artifact this relation originates from.",
    )
    target_artifact_id: str = Field(
        ...,
        description="ID of the artifact this relation points to.",
    )
    relation_type: RelationType = Field(
        ...,
        description="Semantic type of this relationship.",
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Strength of this relationship (0.0–1.0).",
    )
    reasoning: str = Field(
        default="",
        description="The agent's justification for asserting this relation.",
    )
