"""
Base artifact model — the common foundation for every node in the
knowledge graph.

Every artifact tracks who created it, when, how confident the creator
was, its lifecycle status, and what it was derived from. This ensures
full provenance tracing across the entire research graph.
"""

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


# Valid lifecycle states for any artifact
ArtifactStatus = Literal["active", "refuted", "superseded", "merged"]


class BaseArtifact(BaseModel):
    """
    Common fields shared by all knowledge graph nodes.

    Subclasses add domain-specific fields (e.g., Hypothesis adds
    supporting_evidence). The base ensures every node is identifiable,
    timestamped, attributed, and traceable.
    """

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="Unique identifier for this artifact.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of creation.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of last update.",
    )
    created_by: str = Field(
        ...,
        description="ID of the agent that created this artifact.",
    )
    session_id: str = Field(
        default="",
        description="Research session this artifact belongs to.",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Creator's confidence in this artifact (0.0–1.0).",
    )
    status: ArtifactStatus = Field(
        default="active",
        description="Lifecycle status — active artifacts are current; "
        "refuted/superseded ones are kept for provenance.",
    )
    provenance: list[str] = Field(
        default_factory=list,
        description="IDs of artifacts this was derived from.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Free-form tags for categorisation and filtering.",
    )

    def neo4j_properties(self) -> dict:
        """
        Serialize to a flat dict suitable for Neo4j node properties.

        Neo4j doesn't support nested objects, so lists are kept as-is
        (Neo4j handles string lists natively) and datetimes become
        ISO-8601 strings.
        """
        props = self.model_dump()
        props["created_at"] = self.created_at.isoformat()
        props["updated_at"] = self.updated_at.isoformat()
        return props
