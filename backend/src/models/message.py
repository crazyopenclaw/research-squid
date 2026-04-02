"""
Message model — typed, direct agent-to-agent communication.

Unlike published artifacts (Notes, Hypotheses), Messages represent
direct dialogue between agents during debate rounds. They're stored
in the graph for full traceability but also trigger priority attention
from the target agent.

Messages carry a type (objection, evidence, question, etc.) so that
receiving agents can prioritize and route them appropriately — e.g.,
objections get processed before acknowledgments.
"""

from enum import Enum

from pydantic import Field

from src.models.base import BaseArtifact


class MessageType(str, Enum):
    """
    The intent of an agent-to-agent message.

    Types control routing priority: objections and dependency warnings
    are shown first to receiving agents, while acknowledgments are
    shown last.
    """

    OBJECTION = "objection"               # Challenges a claim or hypothesis
    EVIDENCE = "evidence"                 # Provides supporting/counter-evidence
    QUESTION = "question"                 # Asks for clarification
    ACKNOWLEDGMENT = "acknowledgment"     # Confirms receipt or agreement
    REPLICATION_REQUEST = "replication_request"  # Asks to replicate a result
    DEPENDENCY_WARNING = "dependency_warning"    # Flags a dependency issue

    @classmethod
    def from_llm(cls, value: str) -> "MessageType":
        """
        Parse a message type from LLM output, with fallback to QUESTION.

        LLMs sometimes return synonyms or unexpected values. This maps
        common variants to the closest valid type.
        """
        value = value.strip().lower().replace(" ", "_").replace("-", "_")

        try:
            return cls(value)
        except ValueError:
            pass

        synonyms = {
            "challenge": cls.OBJECTION,
            "disagree": cls.OBJECTION,
            "counter": cls.OBJECTION,
            "critique": cls.OBJECTION,
            "proof": cls.EVIDENCE,
            "data": cls.EVIDENCE,
            "support": cls.EVIDENCE,
            "ask": cls.QUESTION,
            "clarify": cls.QUESTION,
            "clarification": cls.QUESTION,
            "ack": cls.ACKNOWLEDGMENT,
            "agree": cls.ACKNOWLEDGMENT,
            "confirm": cls.ACKNOWLEDGMENT,
            "replicate": cls.REPLICATION_REQUEST,
            "reproduce": cls.REPLICATION_REQUEST,
            "warning": cls.DEPENDENCY_WARNING,
            "dependency": cls.DEPENDENCY_WARNING,
            "blocked": cls.DEPENDENCY_WARNING,
        }
        return synonyms.get(value, cls.QUESTION)


# Priority order for displaying messages to agents (lower = shown first)
MESSAGE_PRIORITY = {
    MessageType.DEPENDENCY_WARNING: 0,
    MessageType.OBJECTION: 1,
    MessageType.EVIDENCE: 2,
    MessageType.REPLICATION_REQUEST: 3,
    MessageType.QUESTION: 4,
    MessageType.ACKNOWLEDGMENT: 5,
}


class Message(BaseArtifact):
    """
    A typed, direct message from one agent to another.

    Messages are used during debate to challenge, question, or
    acknowledge another agent's work. They reference specific
    artifacts and trigger the target agent to respond in the
    next cycle. The message_type field enables priority routing.
    """

    from_agent: str = Field(
        ...,
        description="ID of the sending agent.",
    )
    to_agent: str = Field(
        ...,
        description="ID of the target agent.",
    )
    text: str = Field(
        ...,
        description="The message content.",
    )
    message_type: MessageType = Field(
        default=MessageType.QUESTION,
        description="The intent of this message. Controls routing "
        "priority — objections are shown before acknowledgments.",
    )
    regarding_artifact_id: str = Field(
        default="",
        description="ID of the artifact this message is about (if any).",
    )
    read: bool = Field(
        default=False,
        description="Whether the target agent has processed this message.",
    )
