"""
Event types for the event bus.

Every significant action in the research institute emits an event.
The CLI subscribes to display live progress. A future web UI would
subscribe via WebSockets. Events are also persisted to Postgres
for replay and audit.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Categories of events emitted by the research institute."""

    # Artifact lifecycle
    ARTIFACT_CREATED = "artifact_created"
    ARTIFACT_UPDATED = "artifact_updated"
    ARTIFACT_REFUTED = "artifact_refuted"

    # Relations
    RELATION_CREATED = "relation_created"

    # Messages
    MESSAGE_SENT = "message_sent"

    # Source ingestion
    SOURCE_INGESTED = "source_ingested"
    SOURCE_DISCOVERED = "source_discovered"

    # Experiments
    EXPERIMENT_QUEUED = "experiment_queued"
    EXPERIMENT_STARTED = "experiment_started"
    EXPERIMENT_COMPLETED = "experiment_completed"
    EXPERIMENT_FAILED = "experiment_failed"

    # Research cycle
    ITERATION_STARTED = "iteration_started"
    ITERATION_COMPLETED = "iteration_completed"

    # Agent activity
    AGENT_SPAWNED = "agent_spawned"
    AGENT_THINKING = "agent_thinking"
    AGENT_ACTION = "agent_action"

    # Institute lifecycle
    RESEARCH_STARTED = "research_started"
    RESEARCH_COMPLETED = "research_completed"
    STATE_SNAPSHOT = "state_snapshot"
    DEBATE_STARTED = "debate_started"
    DEBATE_COMPLETED = "debate_completed"
    BUDGET_WARNING = "budget_warning"

    # Debate cycle stages
    CLUSTERS_COMPUTED = "clusters_computed"
    INTRA_CLUSTER_REVIEW_STARTED = "intra_cluster_review_started"
    INTRA_CLUSTER_REVIEW_PROGRESS = "intra_cluster_review_progress"
    INTRA_CLUSTER_REVIEW_COMPLETED = "intra_cluster_review_completed"
    INTER_CLUSTER_DEBATE_STARTED = "inter_cluster_debate_started"
    INTER_CLUSTER_DEBATE_PROGRESS = "inter_cluster_debate_progress"
    INTER_CLUSTER_DEBATE_COMPLETED = "inter_cluster_debate_completed"
    COUNTER_RESPONSES_STARTED = "counter_responses_started"
    COUNTER_RESPONSE_PROGRESS = "counter_response_progress"
    COUNTER_RESPONSES_COMPLETED = "counter_responses_completed"
    ADJUDICATION_STARTED = "adjudication_started"
    ADJUDICATION_PROGRESS = "adjudication_progress"
    ADJUDICATION_COMPLETED = "adjudication_completed"
    ADJUDICATING_HYPOTHESIS = "adjudicating_hypothesis"

    # Workspace events
    WORKSPACE_CREATED = "workspace_created"
    WORKSPACE_FILE_WRITTEN = "workspace_file_written"
    WORKSPACE_SCRIPT_EXECUTED = "workspace_script_executed"
    WORKSPACE_SCRIPT_FAILED = "workspace_script_failed"
    WORKSPACE_MEMORY_UPDATED = "workspace_memory_updated"
    WORKSPACE_EXPERIMENT_SUBMITTED = "workspace_experiment_submitted"
    WORKSPACE_SNAPSHOTTED = "workspace_snapshotted"
    WORKSPACE_OPENCODE_SERVER_STARTED = "workspace_opencode_server_started"
    WORKSPACE_OPENCODE_TASK_COMPLETED = "workspace_opencode_task_completed"
    WORKSPACE_OPENCODE_UNAVAILABLE = "workspace_opencode_unavailable"

    # Errors
    ERROR = "error"


class Event(BaseModel):
    """
    A single event emitted by the research institute.

    Events are the sole interface between the core system and any
    UI layer. The core never prints or logs directly — it emits
    events, and subscribers decide how to display them.
    """

    event_type: EventType = Field(
        ...,
        description="What happened.",
    )
    agent_id: str = Field(
        default="",
        description="Which agent caused this event.",
    )
    artifact_id: str = Field(
        default="",
        description="ID of the artifact involved (if any).",
    )
    artifact_type: str = Field(
        default="",
        description="Type name of the artifact (e.g., 'hypothesis').",
    )
    session_id: str = Field(
        default="",
        description="Research session this event belongs to.",
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional event-specific data.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When this event occurred.",
    )
