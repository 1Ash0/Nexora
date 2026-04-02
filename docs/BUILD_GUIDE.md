# BUILD_GUIDE.md
# Step-by-Step Build Instructions for Codex / Antigravity Agents

> **Convention:** Every step has: Objective → Exact Agent Prompt → Expected Output → Failure Modes.
> Steps are sequenced so each one depends only on previously completed steps.
> Never skip a step. Failures compound.

---

## Pre-Build Checklist

Before starting, confirm:
- [ ] Python 3.11+ installed
- [ ] Docker Desktop running
- [ ] Node.js 20+ installed
- [ ] OpenAI API key (set as `OPENAI_API_KEY`)
- [ ] Tavily API key (set as `TAVILY_API_KEY`)
- [ ] Git repo initialized

---

## STEP 1: Environment Bootstrap

**Objective:** All infrastructure services running locally. Agent loop can import config without errors.

**Exact Prompt for Coding Agent:**
```
Create the following files for a Python FastAPI + LangGraph project:

1. `docker-compose.yml` with services:
   - neo4j:5.20-community (ports 7474, 7687; APOC plugin enabled; auth neo4j/research123)
   - qdrant/qdrant:latest (port 6333)
   - redis:7-alpine (port 6379)
   - postgres:15-alpine (port 5432; db=research_db, user=research, password=research123)

2. `backend/config/settings.py` using Pydantic BaseSettings:
   - OPENAI_API_KEY, OPENAI_MODEL (default gpt-4o)
   - TAVILY_API_KEY
   - NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
   - QDRANT_HOST, QDRANT_PORT
   - REDIS_URL
   - DATABASE_URL (PostgreSQL)
   - MAX_ITERATIONS (default 3)
   - EXECUTOR_POOL_SIZE (default 3)
   All values loaded from environment with .env file support.

3. `backend/requirements.txt` with exact pinned versions:
   langgraph==0.2.28, langchain==0.3.7, langchain-openai==0.2.8,
   fastapi==0.115.4, uvicorn[standard]==0.32.0, neo4j==5.26.0,
   qdrant-client==1.12.1, redis==5.2.0, psycopg2-binary==2.9.10,
   tavily-python==0.5.0, pydantic==2.9.2, pydantic-settings==2.6.1,
   structlog==24.4.0, python-dotenv==1.0.1, httpx==0.27.2

4. `scripts/health_check.py` that:
   - Connects to each service (Neo4j, Qdrant, Redis, PostgreSQL)
   - Prints GREEN/RED status per service
   - Exits with code 1 if any service is down

Output all 4 files completely. No placeholders.
```

**Expected Output:**
- `docker-compose up -d` starts 4 containers
- `python scripts/health_check.py` prints 4 green lines
- `from backend.config.settings import settings` imports without error

**Failure Modes:**
| Symptom | Fix |
|---|---|
| Neo4j fails to start | Check APOC plugin env var: `NEO4JLABS_PLUGINS=["apoc"]` |
| Qdrant connection refused | Port 6333 conflict — change to 6334 in compose |
| `pydantic_settings` import error | Ensure `pydantic-settings` separate from `pydantic` in requirements |
| health_check crashes | Add `try/except` per service, print traceback for debugging |

---

## STEP 2: LangGraph State Schema

**Objective:** Single source of truth for agent state. All agents share this schema.

**Exact Prompt:**
```
Create `backend/graph/state.py`.

Define a Python TypedDict `ResearchState` with these exact fields:
- session_id: str
- original_query: str
- refined_query: str
- task_graph: List[TaskItem]  (not Annotated — fully replaced by planner)
- completed_tasks: Annotated[List[TaskItem], operator.add]
- contradictions: Annotated[List[Contradiction], operator.add]
- sources: Annotated[List[dict], operator.add]
- synthesis: str
- iteration_count: int
- interrupt_requested: bool
- human_feedback: Optional[str]
- graph_nodes: Annotated[List[dict], operator.add]
- graph_edges: Annotated[List[dict], operator.add]
- error: Optional[str]
- metadata: dict

Also define these Pydantic models (NOT TypedDicts — these are validated):
- TaskItem: id (UUID str), description, status (Literal pending/running/done/failed),
  priority (int 1–5), dependencies (List[str]), result (Optional[str]),
  confidence (float 0–1), agent_id (Optional[str])
- Contradiction: id (UUID str), source_a, source_b, claim_a, claim_b,
  type (Literal direct/methodological/scope), severity (float 0–1),
  resolution (Optional[str])
- CriticOutput: verdict (Literal pass/replan/retry), overall_score (float),
  coverage_score (float), accuracy_score (float), depth_score (float),
  missing_aspects (List[str]), retry_tasks (List[str]), new_tasks (List[TaskItem])

Add `get_initial_state(query: str, session_id: str) -> ResearchState` function
that returns a valid initial state.

Import operator. Include all necessary imports. No placeholders.
```

**Expected Output:**
```python
from backend.graph.state import ResearchState, get_initial_state
state = get_initial_state("test query", "session-123")
assert state["iteration_count"] == 0
assert state["task_graph"] == []
```

**Failure Modes:**
| Symptom | Fix |
|---|---|
| `TypeError: 'type' object is not subscriptable` | Python < 3.10: use `from __future__ import annotations` |
| `operator.add` not merging | Confirm `Annotated` import from `typing`, not `typing_extensions` |
| Pydantic models crash on import | Ensure Pydantic v2 — check `pydantic.version.VERSION` |

---

## STEP 3: Tool Implementations

**Objective:** Agents have working tools: web search, ArXiv, document loading.

**Exact Prompt:**
```
Create three tool files for a LangChain agent system:

1. `backend/tools/web_search.py`:
   - Function `web_search(query: str, max_results: int = 5) -> List[dict]`
   - Uses Tavily API (tavily-python library)
   - Returns list of {url, title, content, score}
   - Add retry logic: 3 attempts, exponential backoff (1s, 2s, 4s)
   - Raise custom `ToolError` if all retries fail
   - Wrap as LangChain `@tool` with docstring

2. `backend/tools/arxiv_search.py`:
   - Function `arxiv_search(query: str, max_results: int = 5) -> List[dict]`
   - Uses `arxiv` pip package
   - Returns list of {arxiv_id, title, authors, abstract, pdf_url, published}
   - Filter: only papers from last 5 years
   - Wrap as LangChain `@tool`

3. `backend/tools/document_loader.py`:
   - Function `load_url(url: str) -> str`
   - Uses httpx to fetch URL
   - Uses BeautifulSoup to extract main text (strip nav/footer/ads)
   - Chunk into 500-token segments
   - Returns joined text of first 3 chunks
   - Handle: timeout (10s), HTTP errors, non-HTML content
   - Wrap as LangChain `@tool`

4. `backend/tools/__init__.py`:
   - Export `EXECUTOR_TOOLS = [web_search, arxiv_search, load_url]`

Add pip packages needed: arxiv, beautifulsoup4, httpx (already in requirements).
```

**Expected Output:**
```python
from backend.tools import EXECUTOR_TOOLS
results = web_search.invoke({"query": "transformer architecture"})
assert len(results) > 0
assert "url" in results[0]
```

---

## STEP 4: PlannerAgent

**Objective:** Given a research query, produces a validated task graph (DAG) as JSON.

**Exact Prompt:**
```
Create `backend/agents/planner.py`.

Implement `PlannerAgent` class:

__init__(self, llm, settings):
  - Store LLM reference (ChatOpenAI)
  - Load planner prompt from `backend/config/prompts/planner.txt`

plan(self, state: ResearchState) -> dict:
  - Input: state with original_query and optional human_feedback
  - Build prompt: inject query, feedback if present, current iteration count
  - Call LLM with structured output (use .with_structured_output(PlannerOutput))
  - PlannerOutput: { refined_query: str, tasks: List[TaskItem], reasoning: str }
  - Validate: 3–7 tasks, no circular dependencies
  - If validation fails: retry once with error feedback in prompt
  - Return: dict with keys to update ResearchState:
    { refined_query, task_graph, metadata: {plan_reasoning, planned_at} }

Also create `backend/config/prompts/planner.txt`:
```
You are a research planner. Given a research query, decompose it into 3–7 parallel research tasks.

Query: {query}
Iteration: {iteration}
{feedback_section}

Rules:
- Each task must be independently executable by a web researcher
- Tasks should cover different aspects: background, current state, comparisons, limitations, future directions
- Set dependencies as task IDs (empty list if no dependencies)
- Priority 1 = highest

Output valid JSON matching the PlannerOutput schema. No prose.
```

Use `ChatOpenAI(model=settings.OPENAI_MODEL, temperature=0)`.
Handle LLM errors with a fallback: decompose query into 3 generic subtasks.
```

**Expected Output:**
```python
agent = PlannerAgent(llm=ChatOpenAI(), settings=settings)
result = agent.plan(get_initial_state("Compare GPT-4 vs Claude 3", "s1"))
assert 3 <= len(result["task_graph"]) <= 7
assert result["task_graph"][0]["status"] == "pending"
```

---

## STEP 5: ExecutorAgent

**Objective:** Takes a single `TaskItem`, runs tools, returns structured result.

**Exact Prompt:**
```
Create `backend/agents/executor.py`.

Implement `ExecutorAgent` class:

__init__(self, llm, tools, qdrant_client, settings):
  - Build LangChain ReAct agent with tools
  - Load executor prompt from `backend/config/prompts/executor.txt`

execute(self, task: TaskItem, state: ResearchState) -> dict:
  - Run the ReAct agent with task description as input
  - Parse output: extract claims, sources, confidence
  - Call _dedup_and_store(chunks, session_id) to save to Qdrant
  - Return updated TaskItem (status=done, result=str, confidence=float)
    plus list of source dicts and graph_nodes/edges to add to state

_dedup_and_store(self, chunks: List[str], metadata: dict):
  - Hash each chunk (sha256)
  - Check Qdrant for existing hash in same session
  - Only upsert new chunks

Also create `backend/config/prompts/executor.txt`:
```
You are a research executor. Complete this research task using available tools.

Task: {task_description}
Research Query Context: {original_query}

Instructions:
- Use web_search and arxiv_search to find relevant information
- Use load_url to retrieve full content from promising URLs
- Extract specific claims, statistics, and findings
- Note the source URL for every claim
- Assign a confidence score (0.0–1.0) based on source quality

Provide a comprehensive research result with citations.
```

The agent must return a StructuredOutput with:
- summary: str (200–500 words)
- claims: List[{text: str, source_url: str, confidence: float}]
- confidence: float (overall)
```

---

## STEP 6: CriticAgent

**Exact Prompt:**
```
Create `backend/agents/critic.py`.

Implement `CriticAgent` class:

critique(self, state: ResearchState) -> dict:
  - Input: full ResearchState (completed_tasks, original_query)
  - Prompt the LLM to evaluate:
    1. Coverage: Does the research address all aspects of the query?
    2. Accuracy: Are claims supported by credible sources?
    3. Depth: Is the analysis substantive or surface-level?
    4. Consistency: Are there obvious contradictions?
  - Use .with_structured_output(CriticOutput) (from state.py)
  - Return dict with CriticOutput fields to merge into state

Logic:
- If overall_score >= 0.8 and iteration_count < MAX_ITERATIONS: verdict = "pass"
- If missing_aspects found and iteration < MAX_ITERATIONS: verdict = "replan"
- If specific tasks failed: verdict = "retry"
- If iteration >= MAX_ITERATIONS: force verdict = "pass" (prevent infinite loop)

Create prompt `backend/config/prompts/critic.txt` that instructs the LLM
to be a harsh but fair academic peer reviewer.
```

---

## STEP 7: ContradictionEngine

**Exact Prompt:**
```
Create `backend/agents/contradiction_engine.py`.

Implement `ContradictionEngine` class:

detect(self, state: ResearchState) -> dict:
  - Extract all claims from completed_tasks
  - Get embeddings for all claims (OpenAI ada-002)
  - Compute pairwise cosine similarities
  - For pairs with similarity > 0.75 (potential same topic):
    - Use LLM to determine if they contradict
    - If yes: classify as direct | methodological | scope
    - Assign severity 0.0–1.0
  - Return: { contradictions: List[Contradiction], graph_edges: [...] }

The LLM call for classification must use this prompt:
```
Claim A: {claim_a} (Source: {source_a})
Claim B: {claim_b} (Source: {source_b})

Do these claims contradict each other? If yes:
1. Type: direct (opposite facts), methodological (different methods, opposite conclusions), scope (different scopes presented as universal)
2. Severity: 0.0 (trivial) to 1.0 (fundamental)
3. Brief explanation

Output JSON: {contradicts: bool, type?: str, severity?: float, explanation?: str}
```

Optimize: batch embedding calls (max 100 claims in one API call).
Skip pairs where both sources are the same URL.
```

---

## STEP 8: SynthesizerAgent

**Exact Prompt:**
```
Create `backend/agents/synthesizer.py`.

Implement `SynthesizerAgent` class:

synthesize(self, state: ResearchState) -> dict:
  - Gather: all completed task results, all contradictions, all sources
  - Build synthesis prompt with:
    - Original query
    - All research findings (truncated to 8000 tokens total)
    - List of contradictions with their types and severities
    - Human feedback if present
  - Generate comprehensive research report:
    - Executive Summary (2–3 paragraphs)
    - Key Findings (structured by task)
    - Contradictions and Resolutions (address each one)
    - Confidence Assessment
    - Recommendations for Further Research
    - Citations (all sources used)
  - Return: { synthesis: str, metadata: {synthesized_at, word_count, source_count} }

Use model settings.OPENAI_MODEL with temperature=0.3 (slight creativity for prose).
Max tokens: 4000 for synthesis output.
```

---

## STEP 9: LangGraph Workflow

**Exact Prompt:**
```
Create `backend/graph/workflow.py`.

Build the complete LangGraph StateGraph:

1. Instantiate all agents (PlannerAgent, ExecutorAgent x3, CriticAgent,
   ContradictionEngine, SynthesizerAgent) with shared LLM and clients.

2. Define node functions (thin wrappers):
   - `plan_node(state)` → calls planner.plan(state)
   - `execute_node(state)` → runs all PENDING tasks in parallel using asyncio.gather,
     each executor handles one task, merges results
   - `contradiction_node(state)` → calls contradiction_engine.detect(state)
   - `critique_node(state)` → calls critic.critique(state)
   - `synthesize_node(state)` → calls synthesizer.synthesize(state)
   - `human_feedback_node(state)` → returns state unchanged (LangGraph interrupt here)

3. Build graph:
   graph = StateGraph(ResearchState)
   graph.add_node("plan", plan_node)
   graph.add_node("execute", execute_node)
   graph.add_node("contradiction_check", contradiction_node)
   graph.add_node("critique", critique_node)
   graph.add_node("synthesize", synthesize_node)
   graph.add_node("human_feedback", human_feedback_node)

4. Add edges:
   graph.set_entry_point("plan")
   graph.add_edge("plan", "execute")
   graph.add_edge("execute", "contradiction_check")
   graph.add_edge("contradiction_check", "critique")
   
   def route_critique(state):
       if state["interrupt_requested"]: return "human_feedback"
       verdict = state["metadata"].get("critic_verdict")
       if verdict == "pass": return "synthesize"
       if verdict == "replan" and state["iteration_count"] < 3: return "plan"
       if verdict == "retry": return "execute"
       return "synthesize"  # fallback
   
   graph.add_conditional_edges("critique", route_critique,
     {"synthesize": "synthesize", "plan": "plan", "execute": "execute",
      "human_feedback": "human_feedback"})
   graph.add_edge("human_feedback", "plan")  # after feedback, replan
   graph.add_edge("synthesize", END)

5. Compile with PostgresSaver:
   from langgraph.checkpoint.postgres import PostgresSaver
   checkpointer = PostgresSaver.from_conn_string(settings.DATABASE_URL)
   compiled_graph = graph.compile(checkpointer=checkpointer,
                                   interrupt_before=["human_feedback"])

6. Export: `get_workflow() -> CompiledGraph` function.
```

---

## STEP 10: FastAPI Application

**Exact Prompt:**
```
Create the FastAPI application files:

1. `backend/api/main.py`:
   - FastAPI app with lifespan context manager
   - On startup: initialize Neo4j, Qdrant, Redis, compile LangGraph workflow
   - Include routers: research, stream, graph, control
   - Add CORS middleware (origins from settings)
   - Add structured logging with structlog
   - Health endpoint: GET /health returns {status: ok, services: {...}}

2. `backend/api/routes/research.py`:
   - POST /api/v1/research: validate body, generate session_id (UUID4),
     create initial state, invoke graph in background (asyncio task),
     return {session_id, status: "started"}
   - GET /api/v1/research/{session_id}: fetch current state from checkpointer,
     return as ResearchStateResponse Pydantic model

3. `backend/api/routes/stream.py`:
   - GET /api/v1/stream/{session_id}:
     Returns StreamingResponse with media_type="text/event-stream"
     Subscribes to Redis channel f"session:{session_id}:events"
     Yields SSE-formatted strings: f"data: {json.dumps(event)}\n\n"
     Sends heartbeat every 15s: f"data: {json.dumps({'type':'heartbeat'})}\n\n"
     Handles client disconnect gracefully

4. `backend/api/routes/control.py`:
   - POST /api/v1/interrupt/{session_id}: load checkpoint, set interrupt_requested=True, save
   - POST /api/v1/resume/{session_id}: load checkpoint, inject human_feedback,
     set interrupt_requested=False, re-invoke graph from current node

5. `backend/api/schemas.py`:
   - ResearchRequest: query (str, min 10 chars, max 500), session_id (Optional[str])
   - ResearchResponse: session_id, status, created_at
   - ResumeRequest: feedback (str), action (Literal continue/replan/abort)

Include full error handling: HTTP 404 for unknown sessions, 409 for duplicate sessions,
500 with structured error body.
```

---

## STEP 11: Frontend Core

**Exact Prompt:**
```
Create a Next.js 14 App Router application (TypeScript + Tailwind):

1. `frontend/app/page.tsx`:
   - Clean query input UI: large text area, "Start Research" button
   - On submit: POST to /api/v1/research, redirect to /research/{sessionId}
   - Show recent sessions list from localStorage

2. `frontend/hooks/useSSE.ts`:
   - Custom hook: useSSE(sessionId: string)
   - Creates EventSource to /api/v1/stream/{sessionId}
   - Parses JSON from each SSE event
   - Dispatches to state based on event.type
   - Returns: { events, isConnected, lastEvent }
   - Auto-reconnect: on error, retry after 2s, max 5 retries

3. `frontend/app/research/[sessionId]/page.tsx`:
   - Layout: left panel (AgentTimeline 30%), right panel (KnowledgeGraph 70%)
   - Bottom: SynthesisReport when complete
   - Top bar: query text, status badge, session ID
   - Uses useSSE hook

4. `frontend/lib/types.ts`:
   - TypeScript interfaces matching all backend Pydantic schemas
   - SSEEvent union type with all event types

Dark theme. Professional. Minimal animations.
```

---

## STEP 12: D3 Knowledge Graph

**Exact Prompt:**
```
Create `frontend/components/KnowledgeGraph.tsx`.

Implement a D3 force-directed graph component:

Props: { nodes: GraphNode[], edges: GraphEdge[], onNodeClick: (node) => void }

Types:
- GraphNode: { id, label, type: "concept"|"claim"|"source"|"contradiction", confidence }
- GraphEdge: { source, target, type: "relates_to"|"supports"|"contradicts" }

Implementation:
- Use useRef for SVG container, useEffect for D3 initialization
- D3 force simulation: forceLink, forceManyBody (strength -300), forceCenter
- Node colors: concept=#3B82F6, claim=#10B981, source=#6B7280, contradiction=#EF4444
- Edge styles: contradicts = dashed red stroke, supports = thin gray, relates_to = solid blue
- Node size = 8px base + 4px * confidence score
- Labels: show on hover (tooltip div, not SVG text, for performance)
- Animate new nodes: enter with opacity 0 → 1 over 500ms
- On contradiction edge add: pulsing red animation (CSS keyframe)
- Click node: call onNodeClick with full node data
- Resize observer: redraw on container resize
- Export as React component with useMemo for stable D3 refs

Use pure D3 (no react-force-graph wrapper). The D3 code must be inside useEffect
with proper cleanup. Use `useRef<SVGSVGElement>(null)` for the SVG.
```

---

## STEP 13: AWS Deployment

**Exact Prompt:**
```
Create Terraform infrastructure for AWS ECS Fargate deployment:

Files:
1. `infra/terraform/main.tf`: provider aws, region us-east-1
2. `infra/terraform/variables.tf`: all configurable values
3. `infra/terraform/ecs.tf`:
   - ECS Cluster
   - Task Definition: backend (FastAPI), 1 vCPU, 2GB RAM
   - Task Definition: frontend (Next.js), 0.5 vCPU, 1GB RAM
   - ECS Service: backend (min 2, max 10, target CPU 70%)
   - ECS Service: frontend (min 2, max 6)
   - All secrets from SSM Parameter Store (not hardcoded)

4. `infra/terraform/alb.tf`:
   - ALB with HTTPS listener (ACM cert)
   - Target group: backend (stickiness enabled, duration 86400s — required for SSE)
   - Target group: frontend
   - Path-based routing: /api/* → backend, /* → frontend

5. `infra/terraform/rds.tf`:
   - RDS PostgreSQL 15 (db.t3.medium)
   - Multi-AZ: false (dev), true (prod) — parameterized
   - Automated backups: 7 days

6. `infra/terraform/elasticache.tf`:
   - Redis 7 cluster mode disabled (single node for dev)
   - node type: cache.t3.micro

7. `.github/workflows/deploy.yml`:
   - Trigger: push to main
   - Steps: test → build Docker images → push to ECR → update ECS service
   - Use OIDC for AWS auth (no stored keys)

Also create `backend/Dockerfile` (multi-stage: builder + runtime, < 500MB final)
and `frontend/Dockerfile` (node builder + nginx runtime).
```

---

## Build Validation Order

After completing all steps, run in this exact sequence:

```bash
# 1. Start infrastructure
docker-compose up -d
python scripts/health_check.py

# 2. Run unit tests
cd backend && pytest tests/unit/ -v

# 3. Run integration test (single query end-to-end)
python scripts/integration_test.py --query "What are the latest advances in protein folding?"

# 4. Start API server
uvicorn backend.api.main:app --reload --port 8000

# 5. Test SSE stream
curl -N http://localhost:8000/api/v1/stream/test-session-id

# 6. Start frontend
cd frontend && npm run dev

# 7. Run full E2E test
npx playwright test
```
