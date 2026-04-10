# ResearchSquid — Architecture Overview

> **Generated:** 2026-04-05  
> **Version:** 2.0 — Workspace Layer Integrated  
> **Status:** Production Architecture

---

## 🎯 Executive Summary

ResearchSquid is a **multi-layer multi-agent research system** that combines:

- **Exploratory Workspace Layer** — Per-agent workspaces for thinking, drafting, and iterative exploration
- **Institutional Execution Layer** — Validated Docker sandbox for authoritative experiments
- **Knowledge Graph Layer** — Neo4j-powered shared memory and provenance tracking
- **Orchestration Layer** — LangGraph state machines for parallel agent coordination

```
┌─────────────────────────────────────────────────────────────────────┐
│                        User Research Question                        │
└──────────────────────────────┬──────────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FastAPI Backend (/research)                   │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                  LangGraph Institute Graph                    │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐             │  │
│  │  │  Director  │→ │   Squids   │→ │   Debate   │             │  │
│  │  │ (decompose)│  │ (parallel) │  │  (critique)│             │  │
│  │  └────────────┘  └─────┬──────┘  └────────────┘             │  │
│  │                        │                                      │  │
│  │                  ┌─────▼──────┐  ┌────────────┐             │  │
│  │                  │ Controller │→ │ Synthesizer│             │  │
│  │                  │  (budget)  │  │  (report)  │             │  │
│  │                  └────────────┘  └────────────┘             │  │
│  └──────────────────────────────────────────────────────────────┘  │
└───────────────┬─────────────────────────────────┬─────────────────┘
                │                                 │
        ┌───────▼────────┐              ┌────────▼────────┐
        │ Workspace Layer│              │ Sandbox Layer   │
        │  (Exploration) │              │  (Authority)    │
        └───────┬────────┘              └────────┬────────┘
                │                                 │
        ┌───────▼─────────────────────────────────▼────────┐
        │            Knowledge Graph (Neo4j)               │
        │  • Nodes: Hypotheses, Notes, Findings, Sources   │
        │  • Edges: SUPPORTS, CONTRADICTS, EXTENDS         │
        │  • Provenance: Full audit trail                  │
        └───────────────────────┬──────────────────────────┘
                                ▼
        ┌───────────────────────────────────────────────────┐
        │            Vue 3 Frontend Dashboard               │
        │  • Real-time SSE event stream                     │
        │  • Interactive graph visualization                │
        │  • Agent workspace inspector                      │
        └───────────────────────────────────────────────────┘
```

---

## 🏗️ Three-Layer Architecture

### Layer 1: Workspace Layer (Exploratory)

**Purpose:** Lightweight, iterative exploration and drafting

| Aspect | Details |
|--------|---------|
| **Execution** | Host subprocess (no Docker) |
| **Output → DAG** | Never directly — must submit to sandbox |
| **Memory** | Persisted files per agent |
| **Resource limits** | Soft (timeout, memory) |
| **Authoritative** | No — for exploration only |

**Directory Structure:**
```
workspaces/
└── {session_id}/
    └── {agent_id}/
        ├── memory.md           # Append-only findings log
        ├── goals.md            # Current objectives + status
        ├── hypotheses.md       # Mirror of DAG hypotheses
        ├── beliefs.json        # Confidence values
        ├── notes.md            # Freeform thinking
        ├── scripts/            # Draft code
        ├── data/               # Working datasets
        ├── outputs/            # Generated results
        ├── logs/
        │   ├── opencode_sessions.json   # Session history
        │   └── opencode_conversation.md # Full conversation log
        └── .history/           # File version snapshots
```

**Key Components:**
- `WorkspaceManager` — Create/delete/snapshot workspaces
- `FileTracker` — Version history, diffs
- `OpenCodeServer` — Long-lived `opencode serve` process per workspace
- `OpenCodeSession` — One conversation thread within a server
- `SessionRegistry` — Persistent session history
- `MemoryEnforcer` — Validates memory.md updates
- `AccessControl` — Read-only guard for shared data

---

### Layer 2: Sandbox Layer (Institutional)

**Purpose:** Validated, authoritative experiment execution

| Aspect | Details |
|--------|---------|
| **Execution** | Docker container (`squid-sandbox:latest`) |
| **Output → DAG** | Yes, via `ExperimentResult` → Neo4j |
| **Memory** | Ephemeral container |
| **Resource limits** | Hard (Docker limits) |
| **Authoritative** | Yes — only DAG evidence source |

**Sandbox Runner** (`backend/src/sandbox/runner.py`):
- Docker API with strict isolation
- Security: `--network none`, 256MB RAM, 0.5 CPU
- Timeout: 60s default, 300s hard cap
- Pre-installed: numpy, scipy, pandas, scikit-learn, matplotlib

**Experiment Flow:**
```
Agent proposes ExperimentSpec
    → PostgreSQL experiment_store
    → collect_results node (research_cycle)
    → SandboxRunner executes in Docker
    → ExperimentResult → Neo4j Finding node
```

---

### Layer 3: Knowledge Graph (Shared Memory)

**Neo4j Node Types:**

| Label | Purpose | Key Properties |
|-------|---------|----------------|
| `Source` | PDF/URL metadata | `filename`, `url`, `doc_type` |
| `SourceChunk` | 512-token segment | `content`, `chunk_index` |
| `Note` | Agent observation | `content`, `confidence` |
| `Assumption` | Explicit premise | `content`, `status` |
| `Hypothesis` | **Core unit** — testable claim | `content`, `confidence`, `adjudication_status` |
| `Finding` | Experiment conclusion | `content`, `evidence_type` |
| `Relation` | Typed edge artifact | `relation_type` (SUPPORTS, CONTRADICTS, etc.) |
| `Experiment` | Lifecycle tracking | `status`, `spec` |
| `ExperimentResult` | Validated output | `stdout`, `stderr`, `exit_code` |
| `Message` | Agent communication | `type` (question, counter, suggestion) |

**Universal Properties:**
- `id`, `session_id`, `created_by` (agent_id)
- `created_at`, `updated_at`
- `confidence` (0.0–1.0), `status`

---

## 📁 Directory Structure

```
research-squid/
├── backend/
│   ├── src/
│   │   ├── agents/
│   │   │   ├── director.py        # Session initialization
│   │   │   ├── squid.py           # Core researcher
│   │   │   ├── reviewer.py        # Hypothesis critique
│   │   │   ├── controller.py      # Budget + lifecycle
│   │   │   ├── clustering.py      # Belief clustering
│   │   │   ├── reputation.py      # Agent scoring
│   │   │   └── workspace_tools.py # Workspace interface
│   │   │
│   │   ├── workspace/             # ✨ NEW: Workspace Layer
│   │   │   ├── __init__.py
│   │   │   ├── manager.py         # WorkspaceManager
│   │   │   ├── tracker.py         # FileTracker
│   │   │   ├── opencode.py        # OpenCodeServer + Session
│   │   │   ├── session_registry.py
│   │   │   ├── memory_enforcer.py
│   │   │   ├── access_control.py
│   │   │   └── submitter.py       # Workspace → ExperimentSpec
│   │   │
│   │   ├── api/                   # FastAPI endpoints
│   │   ├── graph/                 # Neo4j repository
│   │   ├── llm/                   # OpenAI-compatible client
│   │   ├── rag/                   # Vector retrieval
│   │   ├── sandbox/               # Docker execution
│   │   ├── orchestration/         # LangGraph state machines
│   │   └── config.py              # Pydantic Settings
│   │
│   └── pyproject.toml
│
├── workspaces/                    # ✨ NEW: Agent workspaces
│   └── {session_id}/{agent_id}/
│
├── frontend/
│   └── src/
│       ├── api/index.js           # HTTP + SSE client
│       ├── components/            # Vue components
│       └── views/                 # Dashboard views
│
├── data/sources/                  # Raw research materials
└── docker-compose.yml             # Neo4j + PostgreSQL
```

---

## 🤖 Agent Layer

### Director
- **Runs:** Once at session start
- **Input:** Research question
- **Output:** `Subproblem[]` + `AgentArchetype[]`
- **Model:** Balanced tier

### Squid (Core Researcher)
**Per-subproblem, per-iteration execution:**

```
┌─────────────────────────────────────────────────────────────┐
│                     Squid Research Cycle                    │
├─────────────────────────────────────────────────────────────┤
│ 1. Retrieve context (RAG + graph)                          │
│ 2. Check unread peer messages                              │
│ 3. [NEW] Read workspace: goals.md, notes.md               │
│ 4. Analyze source material                                 │
│ 5. Produce: notes, hypotheses, relations, experiments      │
│ 6. [NEW] WorkspaceTools: append_memory()                   │
│ 7. [NEW] WorkspaceTools: sync_hypotheses()                 │
│ 8. [NEW] WorkspaceTools: update_beliefs()                  │
│ 9. [NEW] WorkspaceTools: run_opencode_loop() (optional)    │
│ 10. Search new sources (Tavily / arXiv)                    │
└─────────────────────────────────────────────────────────────┘
```

**Persona Properties:**
- `skepticism_level`, `experiment_appetite`, `source_strictness`
- `model_tier` → fast / balanced / powerful

### Reviewer
- Critiques hypotheses during debate
- Routed by belief cluster (O(N × K²) vs O(N²))

### Controller
- Monitors budget consumption
- Pauses agents with consecutive empty cycles
- Decides loop termination

### Synthesizer (method, not agent class)
- Implemented as `_synthesize()` on `InstituteGraphBuilder` — not a separate agent
- Calls `self._llm.complete()` directly with prompt templates
- No persona, no budget tracking, no workspace

---

## 🔄 Orchestration (LangGraph)

### Institute Graph
```
START
  │
  ▼
director_plan ──────────────────────────────────┐
  │                                              │
  ▼                                              │
spawn_squids                                    │
  │                                              │
  ▼                                              │
┌─────────────────────────────────────┐        │
│           RESEARCH LOOP              │        │
│  ┌─────────────────────────────────┐│        │
│  │ research_cycle                  ││        │
│  │   ├─ dispatch_squids (parallel) ││        │
│  │   ├─ collect_results            ││        │
│  │   └─ run_experiments            ││        │
│  └─────────────────────────────────┘│        │
│                ▼                     │        │
│  ┌─────────────────────────────────┐│        │
│  │ debate_cycle                    ││        │
│  │   ├─ compute_clusters           ││        │
│  │   ├─ intra_cluster_review       ││        │
│  │   ├─ inter_cluster_debate       ││        │
│  │   └─ resolve_contradictions     ││        │
│  └─────────────────────────────────┘│        │
│                ▼                     │        │
│         controller_eval              │        │
│                │                     │        │
│         [continue?] ─────────────────┘        │
│                                                │
└────────────────────────────────────────────────┘
  │
  ▼
synthesize_report
  │
  ▼
END
```

---

## 🧠 OpenCode Integration

### Why OpenCode?

OpenCode provides the **primary execution path** for workspace exploration:

| Feature | OpenCode | ForgeCode |
|---------|----------|-----------|
| `-c` working directory flag | ✅ Yes | ❌ No (issue #2662) |
| JSON output (`-f json`) | ✅ Yes | ❌ No (issue #2689) |
| Token usage reporting | ✅ In response | ❌ No |
| Auto-approve mode | ✅ Yes | ✅ Yes |

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    OpenCodeServer                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  `opencode serve --port 0` (OS-assigned port)       │   │
│  │                                                      │   │
│  │  Lifecycle:                                          │   │
│  │  • Started lazily on first task                     │   │
│  │  • Kept alive across all Squid cycles               │   │
│  │  • Stopped at workspace cleanup                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│                           ▼                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  OpenCodeSession (conversation thread)              │   │
│  │                                                      │   │
│  │  • Maintains full context across turns              │   │
│  │  • Persists in SQLite (survives restarts)           │   │
│  │  • Token usage in every response                    │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### HTTP API Endpoints
```
GET  /health                    → server status
POST /session                   → create new session
GET  /session/:id               → get session details
POST /session/:id/message       → send message, stream response
GET  /session/:id/message/diff  → file changes from message
```

### Squid → OpenCode Loop

```
1. Squid produces OpenCodeTask in structured output
2. WorkspaceTools.run_opencode_loop(task):
   a. Get or start OpenCodeServer
   b. Create new session
   c. Send initial_prompt
   d. Review output: expected_output_file exists?
   e. If not satisfied: send review_guidance
   f. Loop up to max_iterations
   g. Record in SessionRegistry + conversation log
3. Squid reads produced files as context next cycle
```

---

## 📊 RAG / Vector Store

### Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                    RAG Retrieval Pipeline                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Query                                                      │
│    │                                                        │
│    ▼                                                        │
│  ┌─────────────────────────────────────┐                   │
│  │ Semantic Search (pgvector)          │                   │
│  │  • 1536-dim embeddings              │                   │
│  │  • text-embedding-3-small           │                   │
│  └─────────────────┬───────────────────┘                   │
│                    ▼                                        │
│  ┌─────────────────────────────────────┐                   │
│  │ Graph Enrichment (Neo4j)            │                   │
│  │  • Traverse relations               │                   │
│  │  • Fetch provenance chains          │                   │
│  │  • Get agent context                │                   │
│  └─────────────────┬───────────────────┘                   │
│                    ▼                                        │
│  Hybrid Results → Agent Context                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Methods
- `retrieve_for_inquiry(query)` — Semantic + graph enrichment
- `retrieve_hypotheses()` — Active hypotheses
- `retrieve_notes()` — Agent observations
- `retrieve_agent_context()` — Agent-specific history

---

## 🔌 API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/research` | Start new session |
| `GET` | `/sessions/{id}` | Session metadata |
| `GET` | `/sessions/{id}/overview` | Agents, budget, coverage |
| `GET` | `/sessions/{id}/graph` | Graph visualization data |
| `GET` | `/sessions/{id}/agents` | List agents |
| `GET` | `/sessions/{id}/stream` | **SSE live updates** |
| `GET` | `/sessions/{id}/report` | Final report |
| `GET` | `/sessions/{id}/memory/search` | Semantic search |
| `POST` | `/sessions/{id}/interview` | Ask specific agent |
| `POST` | `/sessions/{id}/continue` | Extend budget + resume |
| `GET` | `/sessions/{id}/workspace/{agent}` | **Workspace inspector** |

---

## ⚙️ Configuration

### Workspace Settings (`backend/src/config.py`)
```python
workspace_base_path: str = "workspaces"
workspace_keep_after_session: bool = True
workspace_snapshot_on_end: bool = True
workspace_opencode_timeout: int = 120
workspace_opencode_timeout_hard_cap: int = 300
workspace_opencode_model: str = ""  # Empty = OpenCode default
workspace_max_opencode_tasks_per_session: int = 10
workspace_opencode_max_iterations: int = 3
workspace_max_file_size_kb: int = 512
workspace_memory_min_entry_length: int = 20
workspace_memory_max_entries: int = 50
workspace_opencode_max_output_size_kb: int = 1024
```

### LLM Tiers
| Tier | Default Model | Use Case |
|------|--------------|----------|
| `fast` | gpt-4o-mini | Routine operations |
| `balanced` | gpt-4o | Most agent work |
| `powerful` | gpt-4-turbo | Complex reasoning |

### Temperatures
| Role | Temperature |
|------|-------------|
| Director | 0.5 |
| Squid | 0.5 |
| Reviewer | 0.5 |
| Controller | 0.3 |
| Synthesizer | 0.5 |

---

## 🔐 Security Model

### Path Traversal Guard
All workspace file operations go through `_safe_path()`:
```python
def _safe_path(self, agent_id: str, session_id: str, relative_path: str) -> Path:
    resolved = (self._base_path / session_id / agent_id / relative_path).resolve()
    if not resolved.is_relative_to(self._base_path / session_id / agent_id):
        raise PermissionError("Path traversal attempt blocked")
    return resolved
```

### Access Control
- **Read:** Own workspace + shared data roots
- **Write:** Own workspace ONLY
- **memory.md:** Append-only (write raises PermissionError)

### Cross-Squid Isolation
- Each squid has isolated workspace directory
- No cross-agent file conflicts
- Read access to other workspaces (future feature)

---

## 📈 Event System

### Event Types
```
RESEARCH_STARTED
AGENT_SPAWNED
AGENT_THINKING
ARTIFACT_CREATED
EXPERIMENT_STARTED
EXPERIMENT_COMPLETED
DEBATE_STARTED
BUDGET_WARNING
WORKSPACE_CREATED              # ✨ NEW
WORKSPACE_FILE_WRITTEN         # ✨ NEW
WORKSPACE_OPENCODE_SERVER_STARTED  # ✨ NEW
WORKSPACE_OPENCODE_TASK_COMPLETED  # ✨ NEW
WORKSPACE_EXPERIMENT_SUBMITTED # ✨ NEW
```

### Flow
- In-process pub/sub
- Last 1000 events in memory
- Streamed to frontend via SSE

---

## 🛠️ Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI + Uvicorn |
| Orchestration | LangGraph 0.2+ |
| LLM | OpenAI-compatible (AsyncOpenAI) |
| Knowledge Graph | Neo4j 5.15 |
| Vector Store | PostgreSQL 16 + pgvector |
| Workspace Execution | OpenCode (serve mode) |
| Institutional Execution | Docker SDK |
| Ingest | PyMuPDF, BeautifulSoup4 |
| Search | Tavily, arXiv |
| CLI | Typer + Rich |
| Frontend | Vue 3 + Vite + vis-network |
| Config | Pydantic Settings |
| Async I/O | asyncpg, SQLAlchemy[asyncio], async Neo4j |

---

## 📋 Implementation Status

| Component | Status |
|-----------|--------|
| Per-agent workspace | ✅ Implemented |
| Workspace Manager | ✅ Implemented |
| OpenCode Integration | ✅ Implemented |
| File Tracker | ✅ Implemented |
| Memory Enforcer | ✅ Implemented |
| Session Registry | ✅ Implemented |
| Access Control | ✅ Implemented |
| Experiment Submitter | ✅ Implemented |
| Workspace Tools API | ✅ Implemented |
| Workspace inspector endpoint | ✅ Implemented |

---

## 🔗 Key Files Reference

| Component | File Path |
|-----------|-----------|
| Workspace Manager | `backend/src/workspace/manager.py` |
| OpenCode Server | `backend/src/workspace/opencode.py` |
| File Tracker | `backend/src/workspace/tracker.py` |
| Session Registry | `backend/src/workspace/session_registry.py` |
| Memory Enforcer | `backend/src/workspace/memory_enforcer.py` |
| Access Control | `backend/src/workspace/access_control.py` |
| Experiment Submitter | `backend/src/workspace/submitter.py` |
| Workspace Tools | `backend/src/agents/workspace_tools.py` |
| Squid Agent | `backend/src/agents/squid.py` |
| Institute Graph | `backend/src/orchestration/institute_graph.py` |
| Sandbox Runner | `backend/src/sandbox/runner.py` |
| Config | `backend/src/config.py` |

---

## 📖 Related Documentation

- **Implementation Plan:** `docs/architecture/workspace-layer-implementation-plan.md`
- **API Reference:** `docs/api/README.md`
- **Development Guide:** `docs/development/README.md`
