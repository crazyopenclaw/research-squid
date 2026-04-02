# ResearchSquid

ResearchSquid is an institute-style multi-agent research system with:

- a `Program Director` that decomposes a question into agenda items
- `Scientist Agents` that work from explicit public tasks
- shared graph memory in `Neo4j`
- shared retrieval memory and checkpoints in `Postgres + pgvector`
- backend-native FastAPI session APIs for the graph UI
- typed experiment execution through Docker sandbox runs
- an inspection UI that shows graph state, agent activity, and institute progress

## What It Does

You give it a research question. The system creates a research program, assigns work to agents, retrieves shared evidence, reads sources, extracts notes and assumptions, proposes hypotheses and findings, runs quick computational checks, and keeps the resulting public artifacts in a permanent research graph.

## Quick Start

Minimum environment:

- `OPENAI_API_KEY`
- `OPENAI_API_BASE` (optional)
- `OPENAI_MODEL` (optional)
- `FAST_MODEL` / `BALANCED_MODEL` / `POWERFUL_MODEL` (optional)
- `TAVILY_API_KEY` (optional)
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`
- `DATABASE_URL`

Start the local dev stack:

```bash
python scripts/dev.py
```

Quick CLI run:

```bash
python run_cli.py "What mechanisms drive antibiotic resistance?"
```

Or start services manually:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d neo4j postgres
cd backend && python run_server.py
cd frontend && npm run dev
```

## Dev Port Cleanup

If `localhost:3000` or `localhost:8000` is already occupied, clear those listeners before starting the dev stack:

```bash
npm run kill-ports
npm run dev:clean
```

## Institute Flow

- Runtime flow: [docs/research-institute-phase1-flow.md](docs/research-institute-phase1-flow.md)
- Frontend integration plan: [docs/plans/frontend-integration-plan.md](docs/plans/frontend-integration-plan.md)
- Phase 1 plan: [docs/plans/research-institute-phase1.md](docs/plans/research-institute-phase1.md)
- Architecture reference: [docs/reference/hive-research-architecture-v3.md](docs/reference/hive-research-architecture-v3.md)
- Product vision: [docs/reference/whatiwant.md](docs/reference/whatiwant.md)

## Current Phase 1 Runtime

1. FastAPI starts the session and the institute runtime in the background.
2. `Program Director` creates a structured research program.
3. `Scientist Agents` claim work items and act on shared memory.
4. `Neo4j` stores canonical public research artifacts.
5. `Postgres + pgvector` stores retrieval memory, checkpoints, and agenda state.
6. The backend-native API projects overview, graph, agent detail, report, and event resources for the frontend.
7. `sandbox_python` executes quick computational checks.
8. `Cluster + Debate` logic groups findings and schedules critique work.
9. `UI` renders the agent graph, event stream, agenda/program state, and agent inspection traces.

## Use as a Library

```bash
pip install -e backend
```

```python
from src.api.service import ResearchService

service = ResearchService()
```

## Backend-Native UI

The frontend now targets the new backend-native session API:

- `POST /research`
- `GET /sessions/{id}`
- `GET /sessions/{id}/overview`
- `GET /sessions/{id}/graph`
- `GET /sessions/{id}/agents`
- `GET /sessions/{id}/agents/{agent_id}`
- `GET /sessions/{id}/events`
- `GET /sessions/{id}/stream`
- `GET /sessions/{id}/report`
- `GET /sessions/{id}/memory/search`
- `POST /sessions/{id}/interview`

## Design Rule

Public artifacts drive the institute. Hidden heuristics should not.

## Repo Layout

- `backend/` is the only backend codebase.
- `frontend/` is the UI.
- `scripts/` contains the canonical setup/dev entrypoints.
- `.env` at the repo root is the canonical environment file.
- downloaded source files are stored under `data/sources/` at the repo root.
