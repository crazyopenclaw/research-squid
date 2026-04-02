"""
Research cycle subgraph — one iteration of scientific investigation.

This subgraph runs all squid agents in parallel (via Send),
collects their outputs, runs any proposed experiments, and records
findings. It's called repeatedly by the top-level institute graph.
"""

import json
from typing import Any

from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

from src.agents.squid import SquidAgent
from src.config import Settings, settings as default_settings
from src.events.bus import EventBus
from src.graph.repository import GraphRepository
from src.graph.queries import GraphQueries
from src.llm.client import LLMClient
from src.models.agent_state import InstituteState, SquidState
from src.models.events import Event, EventType
from src.rag.indexer import RAGIndexer
from src.rag.retriever import RAGRetriever
from src.sandbox.runner import SandboxRunner
from src.search.arxiv import ArxivSearch
from src.search.tavily import TavilySearch
from src.workspace.manager import WorkspaceManager


class ResearchCycleBuilder:
    """
    Builds the LangGraph subgraph for one research iteration.

    The subgraph:
    1. Dispatches squids in parallel via Send
    2. Collects their outputs
    3. Runs any proposed experiments in the sandbox
    4. Records experiment results as findings

    Usage:
        builder = ResearchCycleBuilder(llm, graph, ...)
        graph = builder.build()
    """

    def __init__(
        self,
        llm: LLMClient,
        graph: GraphRepository,
        queries: GraphQueries,
        retriever: RAGRetriever,
        indexer: RAGIndexer | None,
        event_bus: EventBus,
        sandbox: SandboxRunner,
        tavily: TavilySearch | None = None,
        arxiv_search: ArxivSearch | None = None,
        config: Settings | None = None,
        workspace_manager: WorkspaceManager | None = None,
    ) -> None:
        self._llm = llm
        self._graph = graph
        self._queries = queries
        self._retriever = retriever
        self._indexer = indexer
        self._bus = event_bus
        self._sandbox = sandbox
        self._tavily = tavily
        self._arxiv = arxiv_search
        self._config = config or default_settings
        self._workspace_manager = workspace_manager

        # Default squid agent (no workspace) — used when workspace is disabled
        self._squid = SquidAgent(
            llm=llm,
            graph=graph,
            retriever=retriever,
            indexer=indexer,
            event_bus=event_bus,
            tavily=tavily,
            arxiv_search=arxiv_search,
            config=self._config,
        )

    def build(self) -> StateGraph:
        """Build and return the research cycle subgraph."""

        graph = StateGraph(InstituteState)

        graph.add_node("dispatch_squids", self._dispatch_squids)
        graph.add_node("run_squid", self._run_squid)
        graph.add_node("collect_results", self._collect_results)
        graph.add_node("run_experiments", self._run_experiments)

        graph.add_edge(START, "dispatch_squids")
        graph.add_conditional_edges(
            "dispatch_squids",
            self._fan_out_squids,
            ["run_squid"],
        )
        graph.add_edge("run_squid", "collect_results")
        graph.add_edge("collect_results", "run_experiments")
        graph.add_edge("run_experiments", END)

        return graph

    async def _dispatch_squids(
        self, state: InstituteState
    ) -> dict[str, Any]:
        """Prepare squid dispatch — emit iteration start event."""
        iteration = state.get("iteration", 0)

        await self._bus.publish(Event(
            event_type=EventType.ITERATION_STARTED,
            payload={"iteration": iteration, "phase": "research"},
        ))

        return {}

    def _fan_out_squids(self, state: InstituteState) -> list[Send]:
        """
        Create a Send for each active squid agent.

        Each Send carries the squid's specific state (subproblem,
        agent ID) and dispatches to the run_squid node.
        """
        sends = []
        for agent in state.get("agents", []):
            if agent["status"] != "active":
                continue

            # Find the matching subproblem
            subproblem = None
            for sp in state.get("subproblems", []):
                if sp["id"] == agent["subproblem_id"]:
                    subproblem = sp
                    break

            if not subproblem:
                continue

            squid_state = SquidState(
                agent_id=agent["agent_id"],
                agent_name=agent["name"],
                subproblem=subproblem,
                session_id=state.get("session_id", ""),
                iteration=state.get("iteration", 0),
                budget_remaining=state.get("budget_remaining", 0),
                persona=agent.get("persona", {}),
                iteration_summary=state.get("iteration_summary", ""),
                workspace_path=agent.get("workspace_path", ""),
            )

            sends.append(Send("run_squid", squid_state))

        return sends

    async def _run_squid(
        self, state: SquidState
    ) -> dict[str, Any]:
        """Execute one squid's research cycle."""
        workspace_path = state.get("workspace_path", "")

        if self._workspace_manager and workspace_path:
            from src.workspace.submitter import ExperimentSubmitter
            from src.workspace.memory_enforcer import MemoryEnforcer
            from src.agents.workspace_tools import WorkspaceTools

            agent_id = state["agent_id"]
            session_id = state.get("session_id", "")

            opencode_server = await self._workspace_manager.get_or_start_server(
                agent_id, session_id
            )
            submitter = ExperimentSubmitter(self._graph, self._workspace_manager)
            enforcer = MemoryEnforcer(self._workspace_manager, self._config)

            workspace_tools = WorkspaceTools(
                agent_id=agent_id,
                session_id=session_id,
                workspace_manager=self._workspace_manager,
                opencode_server=opencode_server,
                submitter=submitter,
                enforcer=enforcer,
                event_bus=self._bus,
            )

            squid = SquidAgent(
                llm=self._llm,
                graph=self._graph,
                retriever=self._retriever,
                indexer=self._indexer,
                event_bus=self._bus,
                tavily=self._tavily,
                arxiv_search=self._arxiv,
                config=self._config,
                workspace_tools=workspace_tools,
            )
            return await squid.run(state)

        return await self._squid.run(state)

    async def _collect_results(
        self, state: InstituteState
    ) -> dict[str, Any]:
        """
        Collect artifacts from all squids into the institute state.

        Gathers all experiment IDs from squids' proposals for
        the next step (experiment execution).
        """
        # Pending experiments are already stored in the graph by squids.
        # Query for all pending experiments.
        pending = await self._graph.get_by_label(
            "Experiment",
            filters={
                "status": "pending",
                "session_id": state.get("session_id", ""),
            },
            limit=self._config.graph_pending_experiments_limit,
        )

        return {
            "pending_experiments": [e["id"] for e in pending],
        }

    async def _run_experiments(
        self, state: InstituteState
    ) -> dict[str, Any]:
        """
        Execute all pending experiments in Docker sandboxes.

        Each experiment runs in an isolated container. Results are
        stored back in the graph as ExperimentResult nodes.
        """
        pending_ids = state.get("pending_experiments", [])

        for exp_id in pending_ids:
            exp_data = await self._graph.get(exp_id)
            if not exp_data:
                continue
            input_data = self._decode_input_data(exp_data.get("spec_input_data", ""))

            await self._bus.publish(Event(
                event_type=EventType.EXPERIMENT_STARTED,
                artifact_id=exp_id,
                payload={
                    "hypothesis_id": exp_data.get("hypothesis_id", ""),
                    "expected_outcome": exp_data.get("spec_expected_outcome", ""),
                    "code_preview": exp_data.get("spec_code", "")[:240],
                    "input_data": input_data,
                },
            ))

            try:
                result = await self._sandbox.run_experiment(exp_id, exp_data)

                # Store result in graph
                from src.models.experiment import ExperimentResult
                exp_result = ExperimentResult(
                    experiment_id=exp_id,
                    stdout=result.get("stdout", ""),
                    stderr=result.get("stderr", ""),
                    exit_code=result.get("exit_code", -1),
                    artifacts=result.get("artifacts", {}),
                    execution_time_seconds=result.get("execution_time", 0.0),
                    created_by=exp_data.get("created_by", "system"),
                )
                await self._graph.create(exp_result)
                await self._graph.link_experiment_to_result(
                    exp_id, exp_result.id
                )
                if exp_result.exit_code == 0:
                    await self._graph.update(exp_id, {"status": "completed"})
                    await self._bus.publish(Event(
                        event_type=EventType.EXPERIMENT_COMPLETED,
                        artifact_id=exp_id,
                        payload={
                            "result_id": exp_result.id,
                            "exit_code": exp_result.exit_code,
                            "execution_time": exp_result.execution_time_seconds,
                            "stdout_preview": exp_result.stdout[:240],
                            "stderr_preview": exp_result.stderr[:240],
                            "artifacts": result.get("artifacts", {}),
                            "input_data": input_data,
                        },
                    ))
                else:
                    await self._graph.update(exp_id, {"status": "failed"})
                    await self._bus.publish(Event(
                        event_type=EventType.EXPERIMENT_FAILED,
                        artifact_id=exp_id,
                        payload={
                            "exit_code": exp_result.exit_code,
                            "execution_time": exp_result.execution_time_seconds,
                            "error": (
                                exp_result.stderr
                                or exp_result.stdout
                                or "Experiment exited with a non-zero status."
                            )[:400],
                            "expected_outcome": exp_data.get("spec_expected_outcome", ""),
                            "code_preview": exp_data.get("spec_code", "")[:240],
                            "input_data": input_data,
                            "stdout_preview": exp_result.stdout[:240],
                        },
                    ))

            except Exception as e:
                await self._graph.update(exp_id, {"status": "failed"})
                await self._bus.publish(Event(
                    event_type=EventType.EXPERIMENT_FAILED,
                    artifact_id=exp_id,
                    payload={
                        "error": str(e),
                        "expected_outcome": exp_data.get("spec_expected_outcome", ""),
                        "code_preview": exp_data.get("spec_code", "")[:240],
                        "input_data": input_data,
                    },
                ))

        return {"pending_experiments": []}

    @staticmethod
    def _decode_input_data(raw: Any) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return {}
            if isinstance(parsed, dict):
                return parsed
        return {}
