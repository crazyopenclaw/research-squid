"""HiveResearch Coordinator — FastAPI application factory."""

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from hive.schema.finding import Finding
from hive.schema.experiment import BackendJudgment, ExperimentResult, ExperimentSpec
from hive.schema.session import Session, SessionConfig
from hive.dag.client import DAGClient
from hive.dag.writer import post_finding, write_experiment_spec, post_experiment_result
from hive.dag.reader import get_context, get_frontier, get_paradigm_shifts, get_session_summary
from hive.dag.taxonomy import classify_source_tier


def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


dag_client: Optional[DAGClient] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global dag_client
    dag_client = DAGClient()
    await dag_client.connect()

    # Initialize schema
    schema_path = os.path.join(os.path.dirname(__file__), "..", "dag", "schema.cypher")
    if os.path.exists(schema_path):
        with open(schema_path) as f:
            statements = [s.strip() for s in f.read().split(";") if s.strip() and not s.strip().startswith("--")]
            for stmt in statements:
                try:
                    await dag_client.run(stmt)
                except Exception:
                    pass  # Constraints may already exist

    yield
    await dag_client.close()


def create_app() -> FastAPI:
    """Create FastAPI application."""
    app = FastAPI(
        title="HiveResearch Coordinator",
        description="Two-tier autonomous research system",
        version="0.1.0",
        lifespan=lifespan,
    )

    # --- Session Endpoints ---

    @app.post("/research", response_model=Session)
    async def start_research(config: SessionConfig):
        session = Session(
            id=gen_id("session"),
            question=config.question,
            modality=config.modality,
            llm_budget_usd=config.llm_budget_usd,
            compute_budget_usd=config.compute_budget_usd,
            agent_count=config.agent_count,
            created_at=datetime.utcnow(),
        )
        await dag_client.run(
            """
            MERGE (s:Session {id: $id})
            SET s.question = $question, s.modality = $modality, s.status = $status,
                s.created_at = $created_at, s.llm_budget_usd = $llm_budget_usd,
                s.compute_budget_usd = $compute_budget_usd, s.llm_spent_usd = 0,
                s.compute_spent_usd = 0
            """,
            id=session.id, question=session.question, modality=session.modality,
            status=session.status, created_at=session.created_at.isoformat(),
            llm_budget_usd=session.llm_budget_usd,
            compute_budget_usd=session.compute_budget_usd,
        )
        return session

    @app.get("/session/{session_id}")
    async def get_session(session_id: str):
        records = await dag_client.run("MATCH (s:Session {id: $id}) RETURN s", id=session_id)
        if not records:
            raise HTTPException(status_code=404, detail="Session not found")
        return dict(records[0]["s"])

    @app.post("/session/{session_id}/stop")
    async def stop_session(session_id: str):
        await dag_client.run("MATCH (s:Session {id: $id}) SET s.status = 'stopped'", id=session_id)
        return {"session_id": session_id, "status": "stopped"}

    @app.post("/session/{session_id}/pause")
    async def pause_session(session_id: str):
        await dag_client.run("MATCH (s:Session {id: $id}) SET s.status = 'paused'", id=session_id)
        return {"session_id": session_id, "status": "paused"}

    @app.post("/session/{session_id}/resume")
    async def resume_session(session_id: str):
        await dag_client.run("MATCH (s:Session {id: $id}) SET s.status = 'active'", id=session_id)
        return {"session_id": session_id, "status": "active"}

    @app.get("/session/{session_id}/summary")
    async def summary(session_id: str):
        return {"summary": await get_session_summary(dag_client, session_id)}

    @app.get("/session/{session_id}/dag")
    async def get_dag(session_id: str):
        nodes = await dag_client.run(
            "MATCH (n) WHERE n.session_id = $sid RETURN labels(n) as labels, properties(n) as props",
            sid=session_id,
        )
        edges = await dag_client.run(
            "MATCH (a)-[r]->(b) WHERE a.session_id = $sid OR b.session_id = $sid RETURN a.id as src, type(r) as type, b.id as tgt, properties(r) as props",
            sid=session_id,
        )
        return {
            "nodes": [{"labels": r["labels"], "props": dict(r["props"])} for r in nodes],
            "edges": [{"src": r["src"], "type": r["type"], "tgt": r["tgt"], "props": dict(r["props"])} for r in edges],
        }

    # --- Internal Endpoints (Tier-1 agents) ---

    class FindingRequest(BaseModel):
        claim: str
        confidence: float
        confidence_rationale: str
        evidence_type: str
        source_urls: List[str] = []
        numerical_verification_ran: bool = False
        experiment_run_id: Optional[str] = None
        relates_to: Optional[str] = None
        relation_type: Optional[str] = None
        counter_claim: Optional[str] = None
        session_id: str
        agent_id: str

    @app.post("/internal/finding")
    async def post_finding_endpoint(req: FindingRequest):
        source_tiers = [classify_source_tier(url)[0] for url in req.source_urls]
        finding = Finding(
            id=gen_id("f"),
            session_id=req.session_id,
            agent_id=req.agent_id,
            claim=req.claim,
            confidence=req.confidence,
            confidence_rationale=req.confidence_rationale,
            evidence_type=req.evidence_type,  # type: ignore
            source_urls=req.source_urls,
            source_tiers=source_tiers,
            min_source_tier=min(source_tiers) if source_tiers else 4,
            has_numerical_verification=req.numerical_verification_ran,
            experiment_run_id=req.experiment_run_id,
            relates_to=req.relates_to,
            relation_type=req.relation_type,  # type: ignore
            counter_claim=req.counter_claim,
        )
        fid = await post_finding(dag_client, finding)
        return {"finding_id": fid, "status": "created"}

    @app.post("/internal/experiment")
    async def submit_experiment(spec: ExperimentSpec, session_id: str, agent_id: str):
        spec.id = gen_id("spec")
        spec.session_id = session_id
        spec.submitted_by = agent_id
        spec.submitted_at = datetime.utcnow()
        sid = await write_experiment_spec(dag_client, spec)
        return {"spec_id": sid, "status": "queued"}

    @app.get("/internal/context/{agent_id}")
    async def agent_context(agent_id: str, session_id: str):
        return await get_context(dag_client, session_id, agent_id)

    # --- Backend-facing ---

    @app.get("/internal/experiments/queue")
    async def experiment_queue(session_id: Optional[str] = None):
        if session_id:
            from hive.dag.reader import get_pending_experiments
            exps = await get_pending_experiments(dag_client, session_id)
        else:
            records = await dag_client.run(
                "MATCH (e:Experiment {status: 'pending'}) RETURN e ORDER BY e.submitted_at ASC LIMIT 10"
            )
            exps = [dict(r["e"]) for r in records]
        return {"experiments": exps}

    @app.post("/internal/experiments/{spec_id}/result")
    async def post_result(spec_id: str, result: ExperimentResult):
        result.spec_id = spec_id
        rid = await post_experiment_result(dag_client, result)
        return {"run_id": rid, "status": result.status}

    # --- Health ---

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "hive-research-coordinator"}

    return app


app = create_app()
