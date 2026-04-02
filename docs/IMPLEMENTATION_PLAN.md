# IMPLEMENTATION_PLAN.md
# Research Intelligence Platform — Autonomous Multi-Agent Research System
## Production Implementation Plan

---

## Project Overview

| Attribute | Value |
|---|---|
| Project Name | Research Intelligence Platform (RIP) |
| Architecture Class | Multi-Agent AI System with Live Knowledge Graph |
| Primary Stack | LangGraph · FastAPI · Neo4j · Qdrant · Next.js · AWS |
| Total Build Duration | 4 weeks (MVP) + V2 extensions |
| Interview Positioning | Staff-level AI systems engineering |

---

## Repository Structure (Complete)

```
research-intelligence-platform/
├── backend/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── planner.py              # PlannerAgent: decomposes query → task graph
│   │   ├── executor.py             # ExecutorAgent: runs research subtasks
│   │   ├── critic.py               # CriticAgent: evaluates output quality
│   │   ├── synthesizer.py          # SynthesizerAgent: merges findings
│   │   └── contradiction_engine.py # ContradictionClassifier: detects conflicts
│   ├── graph/
│   │   ├── __init__.py
│   │   ├── state.py                # LangGraph state schema (TypedDict)
│   │   ├── workflow.py             # LangGraph StateGraph definition
│   │   ├── nodes.py                # Node functions (thin wrappers over agents)
│   │   ├── edges.py                # Conditional routing logic
│   │   └── checkpointer.py        # PostgresSaver for HITL + session memory
│   ├── memory/
│   │   ├── __init__.py
│   │   ├── vector_store.py         # Qdrant client + embedding ops
│   │   ├── knowledge_graph.py      # Neo4j driver + Cypher ops
│   │   └── session_store.py        # Redis-backed session continuity
│   ├── api/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app entry point
│   │   ├── routes/
│   │   │   ├── research.py         # POST /research, GET /research/{id}
│   │   │   ├── stream.py           # GET /stream/{session_id} (SSE)
│   │   │   ├── graph.py            # GET /graph/{session_id} (KG snapshot)
│   │   │   └── control.py          # POST /interrupt, POST /resume
│   │   ├── schemas.py              # Pydantic request/response models
│   │   └── middleware.py           # Auth, CORS, rate limiting
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── web_search.py           # Tavily/Serper API wrapper
│   │   ├── arxiv_search.py         # ArXiv paper retrieval
│   │   ├── document_loader.py      # PDF/URL ingestion + chunking
│   │   └── calculator.py           # Numeric reasoning tool
│   ├── config/
│   │   ├── settings.py             # Pydantic BaseSettings
│   │   └── prompts/
│   │       ├── planner.txt
│   │       ├── executor.txt
│   │       ├── critic.txt
│   │       ├── synthesizer.txt
│   │       └── contradiction.txt
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── page.tsx                # Landing + query input
│   │   ├── research/
│   │   │   └── [sessionId]/
│   │   │       └── page.tsx        # Live research view
│   │   └── layout.tsx
│   ├── components/
│   │   ├── QueryInput.tsx
│   │   ├── AgentTimeline.tsx       # SSE-driven step log
│   │   ├── KnowledgeGraph.tsx      # D3 force-directed graph
│   │   ├── ContradictionPanel.tsx  # Conflict alerts
│   │   ├── SynthesisReport.tsx     # Final output renderer
│   │   └── HITLModal.tsx           # Human-in-the-loop interrupt UI
│   ├── hooks/
│   │   ├── useSSE.ts               # SSE connection + event parsing
│   │   └── useGraphUpdates.ts      # D3 graph state management
│   ├── lib/
│   │   ├── api.ts                  # API client
│   │   └── types.ts                # TypeScript types
│   └── package.json
├── infra/
│   ├── terraform/
│   │   ├── main.tf
│   │   ├── ecs.tf                  # ECS Fargate for agents
│   │   ├── rds.tf                  # PostgreSQL for checkpointing
│   │   ├── elasticache.tf          # Redis for session store
│   │   └── variables.tf
│   └── docker-compose.yml          # Local dev environment
├── scripts/
│   ├── seed_graph.py               # Populate Neo4j with test data
│   └── benchmark.py                # Latency + throughput benchmarks
└── docs/
    └── architecture.md
```

---

## Phase 1 — Foundation (Days 1–7)

### Objective
Runnable local dev environment with working agent loop (no frontend, no Neo4j, no persistence).

---

### Week 1 Tasks

#### Task 1.1 — Environment Bootstrap
**Sub-tasks:**
- [ ] Create repo, Python 3.11 venv, install base deps
- [ ] Set up `docker-compose.yml` with: Neo4j 5.x, Qdrant latest, Redis 7, PostgreSQL 15
- [ ] Configure `config/settings.py` (Pydantic BaseSettings, env-based)
- [ ] Validate all services reachable with health-check script

**Expected Output:** All services up, `python scripts/health_check.py` returns 5 green checks.

**Key Dependencies:**
```
langgraph==0.2.x
langchain==0.3.x
langchain-openai==0.2.x
neo4j==5.x
qdrant-client==1.x
fastapi==0.115.x
uvicorn[standard]
redis
psycopg2-binary
tavily-python
```

> **Interview Framing:** "I chose PostgreSQL as the LangGraph checkpointer backend because it gives us ACID guarantees on agent state, enabling exact replay semantics for HITL interrupts — a property you cannot get with in-memory or file-based storage."

---

#### Task 1.2 — LangGraph State Schema
**File:** `backend/graph/state.py`

**Sub-tasks:**
- [ ] Define `ResearchState` TypedDict
- [ ] Include all fields needed by all agents
- [ ] Add `Annotated` list fields with `operator.add` for append semantics

**Schema:**
```python
from typing import TypedDict, Annotated, List, Optional
import operator

class TaskItem(TypedDict):
    id: str
    description: str
    status: str           # pending | running | done | failed
    priority: int
    dependencies: List[str]
    result: Optional[str]
    confidence: float

class Contradiction(TypedDict):
    id: str
    source_a: str
    source_b: str
    claim_a: str
    claim_b: str
    type: str             # direct | methodological | scope
    severity: float       # 0.0–1.0
    resolution: Optional[str]

class ResearchState(TypedDict):
    session_id: str
    original_query: str
    refined_query: str
    task_graph: List[TaskItem]
    completed_tasks: Annotated[List[TaskItem], operator.add]
    contradictions: Annotated[List[Contradiction], operator.add]
    sources: Annotated[List[dict], operator.add]
    synthesis: str
    iteration_count: int
    interrupt_requested: bool
    human_feedback: Optional[str]
    graph_nodes: Annotated[List[dict], operator.add]
    graph_edges: Annotated[List[dict], operator.add]
    error: Optional[str]
    metadata: dict
```

> **Interview Framing:** "The `Annotated[List, operator.add]` pattern is critical — it tells LangGraph to merge lists across parallel branches rather than overwrite them. This is what enables fan-out executor pools without race conditions on state."

---

#### Task 1.3 — PlannerAgent
**File:** `backend/agents/planner.py`

**Sub-tasks:**
- [ ] Implement `PlannerAgent` class with `plan(state)` method
- [ ] Prompt: decompose query into 3–7 parallelizable tasks
- [ ] Output structured JSON task graph (validated with Pydantic)
- [ ] Detect task dependencies, set priority ordering
- [ ] Add self-modification: on critic feedback, add/remove tasks

**Expected Output:** Given query "Compare transformer vs LSTM for time series", produces 5-node task graph with dependency edges.

> **Interview Framing:** "The planner produces a DAG, not a linear list. Dependency-aware scheduling is what lets executors run in parallel without stepping on each other."

---

#### Task 1.4 — ExecutorAgent (Single)
**File:** `backend/agents/executor.py`

**Sub-tasks:**
- [ ] Implement `ExecutorAgent` with tool-calling via LangChain
- [ ] Tools: web_search, arxiv_search, document_loader
- [ ] Retry logic: 3 attempts with exponential backoff
- [ ] Store result + source metadata + confidence score
- [ ] Write result to Qdrant for semantic deduplication

**Expected Output:** Given a task "Find LSTM benchmark results on ETTH1 dataset", returns structured `TaskResult` with citations.

---

#### Task 1.5 — CriticAgent
**File:** `backend/agents/critic.py`

**Sub-tasks:**
- [ ] Implement quality scoring rubric (coverage, accuracy, depth, citation quality)
- [ ] Output: `pass | replan | retry`
- [ ] If `replan`: emit list of missing sub-questions
- [ ] If `retry`: identify which executor failed + why

**Scoring Schema:**
```python
class CriticOutput(BaseModel):
    verdict: Literal["pass", "replan", "retry"]
    overall_score: float      # 0.0–1.0
    coverage_score: float
    accuracy_score: float
    depth_score: float
    missing_aspects: List[str]
    retry_tasks: List[str]    # task IDs to retry
    new_tasks: List[TaskItem] # tasks to add if replanning
```

> **Interview Framing:** "The critic closes the feedback loop. Without it, you have a pipeline, not an agent. The critic is what makes the system self-correcting."

---

#### Task 1.6 — LangGraph Workflow Assembly
**File:** `backend/graph/workflow.py`

**Sub-tasks:**
- [ ] Define `StateGraph(ResearchState)`
- [ ] Add nodes: `plan`, `execute_pool`, `critique`, `synthesize`, `contradiction_check`
- [ ] Add conditional edges from `critique`:
  - score > 0.8 → `synthesize`
  - `replan` → `plan` (max 3 iterations)
  - `retry` → `execute_pool` (specific tasks only)
- [ ] Add `HITL` interrupt before `synthesize`
- [ ] Compile with `PostgresSaver` checkpointer

**Graph Flow:**
```
START
  └─→ plan
        └─→ execute_pool (parallel fan-out)
              └─→ contradiction_check
                    └─→ critique
                          ├─→ synthesize (if pass)
                          ├─→ plan (if replan, iter < 3)
                          └─→ execute_pool (if retry)
                                └─→ END (via synthesize)
```

---

### Phase 1 Deliverables Checklist
- [ ] All 5 agents implemented and unit tested
- [ ] LangGraph workflow compiles without error
- [ ] End-to-end run on test query completes in < 60s
- [ ] Agent loop produces structured `ResearchState` at END node
- [ ] Contradiction detection fires on at least 1 simulated conflict

---

## Phase 2 — Memory & Knowledge Graph (Days 8–14)

### Objective
Persistent memory across sessions. Neo4j knowledge graph updated in real-time during research.

---

#### Task 2.1 — Qdrant Vector Memory
**File:** `backend/memory/vector_store.py`

**Sub-tasks:**
- [ ] Create collection `research_memory` with 1536-dim vectors (OpenAI ada-002)
- [ ] Implement `upsert_chunk(text, metadata)` with content-hash deduplication
- [ ] Implement `semantic_search(query, top_k=10, session_filter=None)`
- [ ] Implement `get_session_context(session_id)` for memory continuity
- [ ] Add MMR reranking to reduce redundancy in retrieval

**Schema:**
```python
# Qdrant payload per vector
{
    "chunk_id": "sha256_hash",
    "session_id": "uuid",
    "task_id": "uuid",
    "source_url": "string",
    "source_type": "web|arxiv|pdf",
    "text": "string",
    "confidence": 0.0–1.0,
    "timestamp": "iso8601"
}
```

> **Interview Framing:** "I use content-hash deduplication at the vector store layer to prevent the executor pool from storing duplicate chunks when multiple agents find the same source. This keeps the knowledge base clean without expensive post-processing."

---

#### Task 2.2 — Neo4j Knowledge Graph
**File:** `backend/memory/knowledge_graph.py`

**Node Types:**
```cypher
(:Concept {id, name, description, confidence, session_id})
(:Source {id, url, title, type, retrieved_at})
(:Claim {id, text, confidence, session_id, task_id})
(:Contradiction {id, type, severity, resolved})
(:Session {id, query, created_at, status})
```

**Relationship Types:**
```cypher
(:Claim)-[:SUPPORTED_BY]->(:Source)
(:Claim)-[:RELATES_TO]->(:Concept)
(:Claim)-[:CONTRADICTS]->(:Claim)
(:Contradiction)-[:INVOLVES]->(:Claim)
(:Session)-[:PRODUCED]->(:Claim)
(:Concept)-[:LINKED_TO]->(:Concept)
```

**Sub-tasks:**
- [ ] Implement `upsert_concept(name, description, session_id)`
- [ ] Implement `add_claim(text, source_ids, concept_ids, confidence)`
- [ ] Implement `add_contradiction(claim_a_id, claim_b_id, type, severity)`
- [ ] Implement `get_graph_snapshot(session_id)` → JSON for D3
- [ ] Implement `cross_session_concept_merge()` for multi-session continuity
- [ ] Add full-text index on `Concept.name` and `Claim.text`

> **Interview Framing:** "Neo4j gives us traversal semantics that a vector store can't provide. When I ask 'what claims contradict each other within 2 hops of concept X', that's a Cypher query taking milliseconds. With vectors alone, that's an approximation requiring multiple round-trips."

---

#### Task 2.3 — Session Memory Continuity
**File:** `backend/memory/session_store.py`

**Sub-tasks:**
- [ ] Redis-backed session registry (TTL: 7 days)
- [ ] On session start: load prior concepts + claims for same user/topic
- [ ] Inject prior context into Planner prompt
- [ ] On session end: persist session summary to Neo4j

---

#### Task 2.4 — ContradictionClassifier
**File:** `backend/agents/contradiction_engine.py`

**Contradiction Types:**
| Type | Definition | Example |
|---|---|---|
| `direct` | Same claim, opposite values | "Accuracy is 94%" vs "Accuracy is 78%" |
| `methodological` | Same question, different methods produce conflict | RCT vs observational study reach opposite conclusions |
| `scope` | Claims true in different scopes presented as universal | "Works on ImageNet" vs "Fails on medical images" |

**Sub-tasks:**
- [ ] Pairwise claim comparison across executor outputs
- [ ] Use embedding similarity to find candidate contradictions (cosine > 0.85)
- [ ] Use LLM to classify type + severity for candidates
- [ ] Write contradictions to Neo4j + ResearchState
- [ ] Emit contradiction events over SSE

> **Interview Framing:** "Three-class contradiction taxonomy is the key differentiator. Most RAG systems just flag 'inconsistency'. Classifying whether a conflict is direct, methodological, or scope-based completely changes how the synthesizer handles it."

---

### Phase 2 Deliverables Checklist
- [ ] Qdrant stores chunks from all executor runs
- [ ] Neo4j shows live graph after research completes
- [ ] Contradictions classified and linked in Neo4j
- [ ] Session 2 loads context from Session 1 on same topic
- [ ] `get_graph_snapshot()` returns valid D3-compatible JSON

---

## Phase 3 — API + Streaming Backend (Days 15–21)

### Objective
Production FastAPI backend with SSE streaming, HITL control endpoints, full observability.

---

#### Task 3.1 — FastAPI Application
**File:** `backend/api/main.py`

**Sub-tasks:**
- [ ] Lifespan handler: initialize Neo4j driver, Qdrant client, Redis, LangGraph workflow
- [ ] Add structured logging (structlog)
- [ ] Add request tracing (OpenTelemetry)
- [ ] Rate limiting (slowapi)
- [ ] CORS configured for frontend origin

---

#### Task 3.2 — Research Endpoints
**File:** `backend/api/routes/research.py`

```
POST /api/v1/research
  Body: { query: str, session_id?: str, config?: ResearchConfig }
  Response: { session_id: str, status: "started" }

GET /api/v1/research/{session_id}
  Response: ResearchState snapshot (current)

DELETE /api/v1/research/{session_id}
  Response: { cancelled: true }
```

---

#### Task 3.3 — SSE Streaming Endpoint
**File:** `backend/api/routes/stream.py`

**Event Types:**
```
data: {"type": "agent_step", "agent": "planner", "payload": {...}}
data: {"type": "task_update", "task_id": "...", "status": "running"}
data: {"type": "contradiction_found", "contradiction": {...}}
data: {"type": "graph_update", "nodes": [...], "edges": [...]}
data: {"type": "interrupt_requested", "reason": "...", "options": [...]}
data: {"type": "synthesis_complete", "report": "..."}
data: {"type": "error", "message": "..."}
```

**Sub-tasks:**
- [ ] `AsyncGenerator` that subscribes to Redis pub/sub channel per session
- [ ] Agents publish events to Redis; SSE endpoint streams to client
- [ ] Heartbeat every 15s to keep connection alive
- [ ] Reconnection with `Last-Event-ID` header support

> **Interview Framing:** "I decoupled the agent pub/sub from the SSE transport using Redis. This means the SSE endpoint is stateless — any backend pod can serve a reconnecting client, which is essential for ECS horizontal scaling."

---

#### Task 3.4 — HITL Control Endpoints
**File:** `backend/api/routes/control.py`

```
POST /api/v1/interrupt/{session_id}
  Body: { reason: str }
  Action: Sets interrupt flag in LangGraph checkpointer

POST /api/v1/resume/{session_id}
  Body: { feedback: str, action: "continue" | "replan" | "abort" }
  Action: Injects human_feedback into state, resumes graph
```

**Sub-tasks:**
- [ ] `interrupt`: update checkpoint state with `interrupt_requested: true`
- [ ] `resume`: load checkpoint, inject feedback, re-invoke graph from interrupt node
- [ ] Guard: only allow resume if session is in `INTERRUPTED` status

> **Interview Framing:** "HITL is architecturally trivial if you've designed correctly — LangGraph checkpointing handles the state persistence. The hard part is the interrupt-resume protocol: you must load the exact checkpoint, not replay from scratch."

---

#### Task 3.5 — Knowledge Graph API
**File:** `backend/api/routes/graph.py`

```
GET /api/v1/graph/{session_id}
  Response: { nodes: [...], edges: [...], metadata: {...} }

GET /api/v1/graph/{session_id}/contradictions
  Response: { contradictions: [...] }

POST /api/v1/graph/query
  Body: { cypher: str }  # Admin only
  Response: { results: [...] }
```

---

### Phase 3 Deliverables Checklist
- [ ] All endpoints return correct responses
- [ ] SSE stream delivers events in < 500ms of agent action
- [ ] HITL interrupt pauses graph; resume continues correctly
- [ ] Load test: 10 concurrent sessions without degradation
- [ ] OpenTelemetry traces visible in Jaeger/Grafana

---

## Phase 4 — Frontend + AWS Deployment (Days 22–28)

### Objective
Production Next.js frontend with live D3 graph. Deployed to AWS ECS Fargate.

---

#### Task 4.1 — Next.js Application Setup
- [ ] `create-next-app` with TypeScript, Tailwind, App Router
- [ ] Install: `d3`, `@tanstack/react-query`, `framer-motion`, `zustand`
- [ ] Configure API base URL from env

---

#### Task 4.2 — Query Input + Session Management
**Component:** `QueryInput.tsx`
- [ ] Text input with query suggestions
- [ ] Submit creates session via `POST /api/v1/research`
- [ ] Redirect to `/research/{sessionId}`

---

#### Task 4.3 — SSE Integration
**Hook:** `useSSE.ts`
- [ ] `EventSource` connection to `/api/v1/stream/{sessionId}`
- [ ] Event dispatch to Zustand store
- [ ] Auto-reconnect with exponential backoff

---

#### Task 4.4 — Live Knowledge Graph (D3)
**Component:** `KnowledgeGraph.tsx`
- [ ] D3 force-directed graph
- [ ] Node types: Concept (blue), Claim (green), Source (gray), Contradiction (red)
- [ ] Edge types: `RELATES_TO` (solid), `CONTRADICTS` (dashed red), `SUPPORTED_BY` (thin gray)
- [ ] Live updates: new nodes animate in, contradiction edges flash
- [ ] Click node → detail panel

> **Interview Framing:** "The D3 graph is not decorative. It externalizes the agent's reasoning — you can see claims accumulate, contradictions appear as red edges, and concepts merge across sources in real time."

---

#### Task 4.5 — Agent Timeline
**Component:** `AgentTimeline.tsx`
- [ ] Vertical step log driven by SSE events
- [ ] Each step: agent name, action, duration, status badge
- [ ] Expandable raw payload per step

---

#### Task 4.6 — HITL Modal
**Component:** `HITLModal.tsx`
- [ ] Fires when SSE delivers `interrupt_requested` event
- [ ] Shows: interrupt reason, current state summary
- [ ] Actions: Continue / Replan (with feedback textarea) / Abort
- [ ] Sends to `POST /api/v1/resume/{sessionId}`

---

#### Task 4.7 — AWS Deployment
**Infrastructure:**
```
VPC
├── Public Subnets → ALB (Application Load Balancer)
├── Private Subnets
│   ├── ECS Fargate (backend, 2 tasks min, 10 max)
│   ├── ECS Fargate (frontend Next.js, 2 tasks min)
│   ├── ElastiCache Redis (Multi-AZ)
│   └── RDS PostgreSQL (Multi-AZ, for LangGraph checkpointer)
└── External Services (via secrets manager)
    ├── Neo4j Aura (managed Neo4j)
    ├── Qdrant Cloud
    └── OpenAI API
```

**Sub-tasks:**
- [ ] Terraform: VPC, subnets, security groups
- [ ] Terraform: ECS task definitions + services
- [ ] Terraform: ALB with sticky sessions (for SSE)
- [ ] Dockerfiles: backend (multi-stage, < 500MB), frontend
- [ ] GitHub Actions: build → push ECR → deploy ECS
- [ ] Secrets: AWS Secrets Manager for all API keys

> **Interview Framing:** "ALB sticky sessions are required for SSE — without them, a reconnecting client could hit a different pod that doesn't have the Redis subscription set up. The 'stateless SSE endpoint via Redis pub/sub' pattern is what makes this work at scale."

---

### Phase 4 Deliverables Checklist
- [ ] Frontend renders live graph updates < 1s latency end-to-end
- [ ] HITL flow works in browser: interrupt → feedback → resume
- [ ] Deployed to AWS, accessible via HTTPS
- [ ] Auto-scaling triggers under load
- [ ] CI/CD pipeline deploys on merge to main

---

## V2 Extensions (Post-MVP)

| Feature | Engineering Value | Interview Angle |
|---|---|---|
| Executor specialization (Legal, Science, Finance personas) | Domain-aware tool selection | "Mixture of Experts at the agent level" |
| Graph-to-Graph cross-session synthesis | Multi-session knowledge accumulation | "Long-term memory with graph merging" |
| Confidence decay over time | Temporal knowledge management | "Knowledge staleness modeling" |
| Streaming synthesis (token-by-token) | UX responsiveness | "Backpressure-aware streaming pipeline" |
| Agent cost budgeting | Cost control per session | "Resource-aware agent scheduling" |
| Evaluation harness with LLM-as-judge | Quality measurement | "Automated eval for agent outputs" |
