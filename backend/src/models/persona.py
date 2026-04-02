"""
Agent persona — rich behavioral profile for each squid agent.

Personas control *how* an agent reasons, not *what* it can do.
They modify prompts (skepticism, evidence preferences, reporting style)
and model selection (fast/balanced/powerful tier), but never affect
tool access, safety rules, or budget limits.

Archetypes are templates; personas are instances with slight variation.
"""

import uuid
from datetime import datetime, timezone, UTC
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from src.config import Settings, settings as default_settings


class AgentPersona(BaseModel):
    """
    Research specialization profile for a squid agent.

    These are strategy/profile fields only.
    They do NOT modify: tool allowlists, backend permissions,
    safety rules, budget limits.
    """

    id: str = Field(
        default_factory=lambda: f"persona_{uuid.uuid4().hex[:8]}",
        description="Unique persona identifier.",
    )
    agent_id: str = Field(
        ...,
        description="ID of the agent this persona belongs to.",
    )
    session_id: str = Field(
        ...,
        description="Research session this persona was created for.",
    )
    archetype_id: Optional[str] = Field(
        default=None,
        description="ID of the archetype this persona was instantiated from.",
    )
    origin: Literal["generated", "manual"] = Field(
        default="generated",
        description="Whether this persona was LLM-generated or manually created.",
    )
    revision: int = Field(
        default=1,
        description="Revision number — incremented on persona updates.",
    )

    # ── Strategy fields (editable, affect behavior via prompts) ──────

    specialty: str = Field(
        default_factory=lambda: default_settings.persona_default_specialty,
        description="Research domain specialization, e.g. 'pharmacology', "
        "'methods_skeptic', 'cost_analysis'.",
    )
    skepticism_level: float = Field(
        default_factory=lambda: default_settings.persona_default_skepticism_level,
        ge=0.0,
        le=1.0,
        description="How aggressively the agent questions assumptions. "
        "0.0 = trusting, 1.0 = deeply skeptical.",
    )
    preferred_evidence_types: List[str] = Field(
        default_factory=lambda: list(
            default_settings.persona_default_preferred_evidence_types
        ),
        description="Types of evidence this agent values most.",
    )
    contradiction_aggressiveness: float = Field(
        default_factory=lambda: (
            default_settings.persona_default_contradiction_aggressiveness
        ),
        ge=0.0,
        le=1.0,
        description="Tendency to actively seek counter-evidence and "
        "challenge consensus. 0.0 = agreeable, 1.0 = combative.",
    )
    source_strictness: float = Field(
        default_factory=lambda: default_settings.persona_default_source_strictness,
        ge=0.0,
        le=1.0,
        description="Preference for tier-1/2 sources over informal ones. "
        "0.0 = accepts anything, 1.0 = only peer-reviewed.",
    )
    experiment_appetite: float = Field(
        default_factory=lambda: default_settings.persona_default_experiment_appetite,
        ge=0.0,
        le=1.0,
        description="Tendency to propose experiments vs pure reasoning. "
        "0.0 = theoretical, 1.0 = empiricist.",
    )
    reporting_style: str = Field(
        default_factory=lambda: default_settings.persona_default_reporting_style,
        description="Output style: 'concise', 'detailed', or 'critical'.",
    )
    motivation: str = Field(
        default_factory=lambda: default_settings.persona_default_motivation,
        description="Primary drive: 'truth_seeking', 'novelty', "
        "'consensus_building', 'falsification'.",
    )
    collaboration_style: str = Field(
        default_factory=lambda: default_settings.persona_default_collaboration_style,
        description="How the agent interacts: 'collaborative', "
        "'independent', 'adversarial', 'mentoring'.",
    )
    risk_tolerance: float = Field(
        default_factory=lambda: default_settings.persona_default_risk_tolerance,
        ge=0.0,
        le=1.0,
        description="Willingness to pursue bold, uncertain directions. "
        "0.0 = conservative, 1.0 = risk-seeking.",
    )
    novelty_bias: float = Field(
        default_factory=lambda: default_settings.persona_default_novelty_bias,
        ge=0.0,
        le=1.0,
        description="Preference for unconventional ideas over established "
        "approaches. 0.0 = orthodox, 1.0 = contrarian.",
    )

    # ── Model selection (same provider, different models) ────────────

    model_tier: Literal["fast", "balanced", "powerful"] = Field(
        default_factory=lambda: default_settings.persona_default_model_tier,
        description="LLM tier for this persona. Maps to model names "
        "configured in Settings (fast_model, balanced_model, powerful_model).",
    )
    model_name: Optional[str] = Field(
        default=None,
        description="Override: specific model name (e.g. 'gpt-4o'). "
        "If set, takes precedence over model_tier.",
    )

    # ── System fields (NOT editable by agents) ───────────────────────

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this persona was created.",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="When this persona was last modified.",
    )
    revision_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Log of previous revisions for auditability.",
    )


def create_persona(
    agent_id: str,
    session_id: str,
    config: Settings | None = None,
) -> AgentPersona:
    """
    Create a manual persona using explicit defaults only.

    Use this for quick testing or when the Director hasn't generated
    archetypes. All trait values start at their defaults.
    """
    cfg = config or default_settings
    return AgentPersona(
        id=f"persona_{uuid.uuid4().hex[:8]}",
        agent_id=agent_id,
        session_id=session_id,
        origin="manual",
        specialty=cfg.persona_default_specialty,
        preferred_evidence_types=list(cfg.persona_default_preferred_evidence_types),
        skepticism_level=cfg.persona_default_skepticism_level,
        contradiction_aggressiveness=cfg.persona_default_contradiction_aggressiveness,
        source_strictness=cfg.persona_default_source_strictness,
        experiment_appetite=cfg.persona_default_experiment_appetite,
        reporting_style=cfg.persona_default_reporting_style,
        motivation=cfg.persona_default_motivation,
        collaboration_style=cfg.persona_default_collaboration_style,
        risk_tolerance=cfg.persona_default_risk_tolerance,
        novelty_bias=cfg.persona_default_novelty_bias,
        model_tier=cfg.persona_default_model_tier,
    )


def generate_persona_prompt(
    persona: AgentPersona,
    config: Settings | None = None,
) -> str:
    """
    Generate a persona-specific addition to the agent system prompt.

    Converts the numeric trait vector into natural language behavioral
    instructions. Conditional rules fire at trait thresholds to give
    the LLM concrete behavioral guidance, not just numbers.

    Returns a markdown block suitable for prepending to SQUID_SYSTEM.
    """
    cfg = config or default_settings
    lines = [
        "## Your Research Persona",
        f"- **Specialty:** {persona.specialty}",
        f"- **Skepticism level:** {persona.skepticism_level:.0%}",
        f"- **Preferred evidence:** {', '.join(persona.preferred_evidence_types)}",
        f"- **Source strictness:** {persona.source_strictness:.0%} "
        f"(preference for tier-1/2 sources)",
        f"- **Experiment appetite:** {persona.experiment_appetite:.0%} "
        f"(tendency to propose experiments)",
        f"- **Reporting style:** {persona.reporting_style}",
        f"- **Motivation:** {persona.motivation}",
        f"- **Collaboration style:** {persona.collaboration_style}",
    ]

    # Conditional behavioral rules — fire at high/low thresholds
    if persona.skepticism_level > cfg.persona_high_threshold:
        lines.append(
            "- You are naturally skeptical. Question assumptions aggressively."
        )
    elif persona.skepticism_level < cfg.persona_low_threshold:
        lines.append(
            "- You tend to trust established findings. Focus on building "
            "on existing work rather than tearing it down."
        )

    if persona.contradiction_aggressiveness > cfg.persona_high_threshold:
        lines.append(
            "- You actively seek counter-evidence and challenge consensus "
            "positions."
        )
    elif persona.contradiction_aggressiveness < cfg.persona_low_threshold:
        lines.append(
            "- You prefer to find agreement and common ground with other "
            "agents' work."
        )

    if persona.source_strictness > cfg.persona_source_strictness_threshold:
        lines.append(
            "- You strongly prefer tier-1 and tier-2 sources. Flag weak "
            "sources prominently."
        )

    if persona.experiment_appetite > cfg.persona_high_threshold:
        lines.append(
            "- You prefer empirical validation over theoretical reasoning "
            "alone. Propose experiments whenever possible."
        )
    elif persona.experiment_appetite < cfg.persona_low_threshold:
        lines.append(
            "- You favor theoretical analysis and logical deduction over "
            "empirical experiments."
        )

    if persona.novelty_bias > cfg.persona_high_threshold:
        lines.append(
            "- You are drawn to unconventional but defensible directions. "
            "Challenge orthodoxy when evidence supports it."
        )
    elif persona.novelty_bias < cfg.persona_low_threshold:
        lines.append(
            "- You prefer well-established approaches. Extraordinary claims "
            "require extraordinary evidence."
        )

    if persona.risk_tolerance < cfg.persona_low_threshold:
        lines.append(
            "- You are conservative about bold claims and prefer incremental "
            "conclusions."
        )
    elif persona.risk_tolerance > cfg.persona_high_threshold:
        lines.append(
            "- You are willing to pursue high-risk, high-reward hypotheses "
            "that others might dismiss."
        )

    if persona.reporting_style == "detailed":
        lines.append(
            "- Provide thorough reasoning chains. Show your work."
        )
    elif persona.reporting_style == "critical":
        lines.append(
            "- Focus your reports on weaknesses, gaps, and what's missing."
        )

    return "\n".join(lines)
