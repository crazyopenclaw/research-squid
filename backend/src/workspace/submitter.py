"""
ExperimentSubmitter — bridge from workspace exploration to the institutional pipeline.

When a Squid uses OpenCode to explore something and sees a promising result,
it calls submit() to formally queue the experiment through the existing
ExperimentRun pipeline (research_cycle.py → SandboxRunner → ExperimentResult).

These are ADDITIONAL experiments on top of those the Squid creates directly.
The existing experiment-creation path in SquidAgent is unchanged.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.models.experiment import Experiment, ExperimentSpec

if TYPE_CHECKING:
    from src.graph.repository import GraphRepository
    from src.workspace.manager import WorkspaceManager

# Requirements that are pre-installed in the sandbox image and thus allowed
_ALLOWED_REQUIREMENTS = {
    "numpy", "scipy", "pandas", "scikit-learn", "matplotlib",
    "seaborn", "statsmodels", "networkx", "sympy", "pillow",
}


class ExperimentSubmitter:
    """
    Creates formal Experiment nodes in Neo4j from workspace-originated specs.

    The submitted Experiment nodes have status="pending" and are picked up
    by the existing run_experiments node in ResearchCycleBuilder — no changes
    to the pipeline are needed.

    Tagging: workspace-submitted experiments get source="workspace_exploration"
    in their spec_expected_outcome field prefix so reviewers know they came
    from workspace exploration and are thus "preliminary" (see D10).
    """

    def __init__(
        self,
        graph: "GraphRepository",
        workspace_manager: "WorkspaceManager",
    ) -> None:
        self._graph = graph
        self._manager = workspace_manager

    async def submit(
        self,
        agent_id: str,
        session_id: str,
        hypothesis_id: str,
        spec: ExperimentSpec,
        workspace_script_path: str | None = None,
    ) -> str:
        """
        Validate and submit an ExperimentSpec to the institutional pipeline.

        If workspace_script_path is given, reads the script from the workspace
        and uses its content as the experiment code (overrides spec.code).

        Returns the experiment_id.
        """
        # Read script from workspace if provided
        if workspace_script_path:
            try:
                script_content = await self._manager.read_file(
                    agent_id, session_id, workspace_script_path
                )
                spec = spec.model_copy(update={"code": script_content})
            except FileNotFoundError:
                raise ValueError(
                    f"Workspace script not found: '{workspace_script_path}'"
                )

        self._validate_spec(spec)

        # Tag as workspace-originated (D10: unverified until ExperimentResult)
        tagged_outcome = f"[workspace_exploration] {spec.expected_outcome}"
        spec = spec.model_copy(update={"expected_outcome": tagged_outcome})

        experiment = Experiment(
            hypothesis_id=hypothesis_id,
            spec=spec,
            status="pending",
            created_by=agent_id,
            session_id=session_id,
        )
        await self._graph.create(experiment)
        return experiment.id

    async def list_pending(
        self,
        agent_id: str,
        session_id: str,
    ) -> list[dict[str, Any]]:
        """Return pending experiments submitted by this agent."""
        results = await self._graph.get_by_label(
            "Experiment",
            filters={
                "status": "pending",
                "created_by": agent_id,
                "session_id": session_id,
            },
            limit=50,
        )
        return results

    def _validate_spec(self, spec: ExperimentSpec) -> None:
        """
        Validate an ExperimentSpec before submission.

        Raises ValueError with a descriptive message if invalid.
        """
        if not spec.code.strip():
            raise ValueError("ExperimentSpec.code cannot be empty")

        if spec.timeout_seconds > 300:
            raise ValueError(
                f"ExperimentSpec.timeout_seconds ({spec.timeout_seconds}) "
                f"exceeds maximum of 300 seconds"
            )

        disallowed = [r for r in spec.requirements if r not in _ALLOWED_REQUIREMENTS]
        if disallowed:
            raise ValueError(
                f"ExperimentSpec.requirements contains packages not in the "
                f"sandbox allow-list: {disallowed}. "
                f"Allowed: {sorted(_ALLOWED_REQUIREMENTS)}"
            )
