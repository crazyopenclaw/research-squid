"""
Note model — an agent's annotation or observation on source material.

Notes are the first interpretive layer: an agent reads source chunks
and records what it observes, questions, or finds interesting. Notes
ground higher-level artifacts like Assumptions and Hypotheses.
"""

from pydantic import Field

from src.models.base import BaseArtifact


class Note(BaseArtifact):
    """
    An agent's observation or annotation on one or more source chunks.

    Notes bridge raw source material and higher-level reasoning.
    An agent creates a Note after reading chunks, capturing insights
    that will later inform Assumptions and Hypotheses.
    """

    text: str = Field(
        ...,
        description="The note's content — what the agent observed or inferred.",
    )
    source_chunk_ids: list[str] = Field(
        default_factory=list,
        description="IDs of the SourceChunks this note is based on.",
    )
    embedding_id: str = Field(
        default="",
        description="ID in the pgvector embeddings table.",
    )
