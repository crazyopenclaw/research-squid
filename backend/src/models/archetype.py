"""
Archetype — reusable template for spawning agent personas.

The Director generates up to 20 archetypes per research session,
each representing a distinct research perspective or methodology.
Personas are then instantiated from archetypes with slight trait
randomization to ensure diversity even among agents sharing an
archetype.

Example archetypes for a medical research question:
  - "Pharmacology Empiricist" (high experiment_appetite, low novelty_bias)
  - "Methods Skeptic" (high skepticism, high source_strictness)
  - "Cross-Disciplinary Theorist" (high novelty_bias, low source_strictness)
"""

import random
import uuid
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field

from src.config import settings as default_settings
from src.models.persona import AgentPersona


class Archetype(BaseModel):
    """
    A template for creating agent personas with coherent trait profiles.

    Archetypes define base trait values and a variance range. When an
    agent is spawned from an archetype, each trait is randomized within
    [base - variance, base + variance] (clamped to 0.0–1.0) to create
    natural diversity among agents of the same type.
    """

    id: str = Field(
        default_factory=lambda: f"arch_{uuid.uuid4().hex[:8]}",
        description="Unique archetype identifier.",
    )
    name: str = Field(
        ...,
        description="Human-readable archetype name, e.g. 'Methods Skeptic'.",
    )
    description: str = Field(
        ...,
        description="What this archetype brings to the institute — its "
        "unique research perspective and methodology.",
    )

    # Default trait values (personas get these ± variance)
    base_traits: Dict[str, float] = Field(
        default_factory=lambda: {
            "skepticism_level": default_settings.persona_default_skepticism_level,
            "contradiction_aggressiveness": (
                default_settings.persona_default_contradiction_aggressiveness
            ),
            "source_strictness": default_settings.persona_default_source_strictness,
            "experiment_appetite": default_settings.persona_default_experiment_appetite,
            "risk_tolerance": default_settings.persona_default_risk_tolerance,
            "novelty_bias": default_settings.persona_default_novelty_bias,
        },
        description="Base trait values. Keys must match AgentPersona "
        "float trait field names.",
    )
    trait_variance: float = Field(
        default_factory=lambda: default_settings.archetype_trait_variance,
        ge=0.0,
        le=0.3,
        description="How much to randomize traits when spawning a persona. "
        "Higher variance = more diversity within archetype.",
    )

    # Non-numeric defaults
    suggested_specialties: List[str] = Field(
        default_factory=lambda: [default_settings.persona_default_specialty],
        description="Domain specializations this archetype is suited for.",
    )
    suggested_evidence_types: List[str] = Field(
        default_factory=lambda: list(
            default_settings.persona_default_preferred_evidence_types
        ),
        description="Evidence types this archetype prefers.",
    )
    reporting_style: str = Field(
        default_factory=lambda: default_settings.persona_default_reporting_style,
        description="Default reporting style: 'concise', 'detailed', 'critical'.",
    )
    motivation: str = Field(
        default_factory=lambda: default_settings.persona_default_motivation,
        description="Primary drive for this archetype.",
    )
    collaboration_style: str = Field(
        default_factory=lambda: default_settings.persona_default_collaboration_style,
        description="Default interaction style.",
    )
    model_tier: Literal["fast", "balanced", "powerful"] = Field(
        default_factory=lambda: default_settings.persona_default_model_tier,
        description="Default LLM tier for agents of this archetype.",
    )


def spawn_persona_from_archetype(
    archetype: Archetype,
    agent_id: str,
    session_id: str,
    specialty_override: str | None = None,
) -> AgentPersona:
    """
    Create an AgentPersona from an archetype template.

    Each numeric trait is randomized within [base ± variance], clamped
    to [0.0, 1.0]. Non-numeric fields (specialty, evidence types, etc.)
    are copied directly from the archetype.

    Args:
        archetype: The template to instantiate from.
        agent_id: ID of the agent receiving this persona.
        session_id: Current research session ID.
        specialty_override: If set, overrides the archetype's specialty.

    Returns:
        A new AgentPersona with randomized traits.
    """
    # Randomize numeric traits within variance bounds
    traits: Dict[str, float] = {}
    for trait_name, base_value in archetype.base_traits.items():
        delta = random.uniform(-archetype.trait_variance, archetype.trait_variance)
        traits[trait_name] = max(0.0, min(1.0, base_value + delta))

    # Pick a specialty — use override, or randomly select from suggestions
    specialty = specialty_override or random.choice(archetype.suggested_specialties)

    return AgentPersona(
        agent_id=agent_id,
        session_id=session_id,
        archetype_id=archetype.id,
        origin="generated",
        specialty=specialty,
        skepticism_level=traits.get(
            "skepticism_level",
            default_settings.persona_default_skepticism_level,
        ),
        contradiction_aggressiveness=traits.get(
            "contradiction_aggressiveness",
            default_settings.persona_default_contradiction_aggressiveness,
        ),
        source_strictness=traits.get(
            "source_strictness",
            default_settings.persona_default_source_strictness,
        ),
        experiment_appetite=traits.get(
            "experiment_appetite",
            default_settings.persona_default_experiment_appetite,
        ),
        risk_tolerance=traits.get(
            "risk_tolerance",
            default_settings.persona_default_risk_tolerance,
        ),
        novelty_bias=traits.get(
            "novelty_bias",
            default_settings.persona_default_novelty_bias,
        ),
        preferred_evidence_types=list(archetype.suggested_evidence_types),
        reporting_style=archetype.reporting_style,
        motivation=archetype.motivation,
        collaboration_style=archetype.collaboration_style,
        model_tier=archetype.model_tier,
    )


def parse_archetypes_from_llm(raw: List[Dict[str, Any]]) -> List[Archetype]:
    """
    Parse archetype dicts from Director LLM output into Archetype models.

    Handles missing fields gracefully — the Director may not produce
    every field, so we fall back to defaults.
    """
    archetypes: List[Archetype] = []
    for data in raw:
        # Extract base traits from the LLM output
        base_traits = {}
        for trait in [
            "skepticism_level",
            "contradiction_aggressiveness",
            "source_strictness",
            "experiment_appetite",
            "risk_tolerance",
            "novelty_bias",
        ]:
            if trait in data:
                base_traits[trait] = max(0.0, min(1.0, float(data[trait])))

        archetype = Archetype(
            id=data.get("id", f"arch_{uuid.uuid4().hex[:8]}"),
            name=data.get("name", "Unnamed Archetype"),
            description=data.get("description", ""),
            base_traits=base_traits or Archetype.model_fields["base_traits"].default_factory(),
            trait_variance=data.get(
                "trait_variance", default_settings.archetype_trait_variance
            ),
            suggested_specialties=data.get(
                "suggested_specialties",
                [default_settings.persona_default_specialty],
            ),
            suggested_evidence_types=data.get(
                "suggested_evidence_types",
                list(default_settings.persona_default_preferred_evidence_types),
            ),
            reporting_style=data.get(
                "reporting_style", default_settings.persona_default_reporting_style
            ),
            motivation=data.get(
                "motivation", default_settings.persona_default_motivation
            ),
            collaboration_style=data.get(
                "collaboration_style",
                default_settings.persona_default_collaboration_style,
            ),
            model_tier=data.get("model_tier", default_settings.persona_default_model_tier),
        )
        archetypes.append(archetype)

    return archetypes
