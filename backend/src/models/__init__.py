"""
Pydantic data models defining the full knowledge graph ontology.

Every artifact in the research institute — from raw source chunks to
refined hypotheses to experiment results — is a typed Pydantic model
that maps 1:1 to a Neo4j node.
"""

from src.models.base import BaseArtifact
from src.models.source import Source, SourceChunk
from src.models.note import Note
from src.models.claim import Assumption, Hypothesis, Finding
from src.models.relation import Relation, RelationType
from src.models.experiment import ExperimentSpec, ExperimentResult
from src.models.message import Message
from src.models.events import Event, EventType

__all__ = [
    "BaseArtifact",
    "Source",
    "SourceChunk",
    "Note",
    "Assumption",
    "Hypothesis",
    "Finding",
    "Relation",
    "RelationType",
    "ExperimentSpec",
    "ExperimentResult",
    "Message",
    "Event",
    "EventType",
]
