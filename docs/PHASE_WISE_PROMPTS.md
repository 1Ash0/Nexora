# PHASE_WISE_PROMPTS.md
# Copy-Paste Ready Prompts for Every Build Phase

> Each section contains: Claude (architecture/reasoning) prompts, Codex (code generation) prompts, and Antigravity (workflow automation) prompts.
> Use Claude prompts when you need to reason about design decisions first.
> Use Codex prompts when generating code.
> Use Antigravity prompts when orchestrating multi-file builds.

---

## PHASE 1: Core Agent Loop

### P1-CL-1 — Architecture Decision: LangGraph vs Custom Orchestrator

```
You are a Staff AI Systems Architect at a FAANG company.

I am building a multi-agent research system. I need to choose between:
A) LangGraph (StateGraph with typed state)
B) Custom orchestrator (Python async, manual state management)
C) CrewAI
D) AutoGen

Evaluate each against these requirements:
1. Typed shared state across 5 agents (Planner, Executor, Critic, Synthesizer, Contradiction Engine)
2. Human-in-the-loop interrupt and resume with state persistence
3. Conditional routing: Critic decides whether to replan, retry, or synthesize
4. Parallel executor fan-out (3 executors running simultaneously)
5. PostgreSQL-backed checkpointing for session continuity
6. Production-grade: restartable, observable, testable

For each option: list pros, cons, and the exact failure mode under my requirements.
Then recommend one with technical justification.
Do not give generic answers. Be specific about LangGraph APIs.
```

---

### P1-CL-2 — State Design: Annotated vs Regular Fields

```
I am designing a LangGraph ResearchState TypedDict for a multi-agent research system.

Some fields are updated by a single agent (e.g., task_graph is replaced by Planner).
Some fields are accumulated across parallel agents (e.g., completed_tasks, sources).

Explain:
1. The exact behavior of `Annotated[List[X], operator.add]` in LangGraph state merging
2. When to use regular List vs Annotated List — give concrete examples from my system
3. What happens if two executor agents update `completed_tasks` simultaneously without Annotated
4. How LangGraph handles branch/merge for parallel nodes at the state level
5. Any performance implications of large Annotated lists (>1000 items)

Be specific. Include code examples.
```

---

### P1-CDX-1 — Planner Agent Code Generation

```
Generate a complete, production-ready PlannerAgent for a LangGraph multi-agent research system.

File: backend/agents/planner.py

Requirements:
- Class: PlannerAgent
- Method: plan(state: ResearchState) -> dict
- Uses ChatOpenAI with .with_structured_output() for typed output
- Output schema: PlannerOutput(BaseModel) with refined_query, tasks: List[TaskItem], reasoning
- Validates task count (3–7) and dependency graph (no cycles)
- Detects cycles using DFS on dependency graph
- Fallback: if LLM fails twice, generate 3 generic subtasks from query keywords
- Logs: structlog with session_id, iteration, task_count
- Returns state update dict (only keys that change)

Planner prompt (inject into system prompt):
"You are a research decomposition specialist. Break the given query into 3–7 parallel, 
independently-executable research tasks. Each task must have a clear search strategy.
Set dependencies only when task B genuinely requires task A's output.
Priority 1 = most critical. Output JSON only."

Include all imports. Type every function. No placeholders. Production quality.
```

---

### P1-CDX-2 — Executor Agent with Tool Loop

```
Generate a complete ExecutorAgent for a LangGraph multi-agent research system.

File: backend/agents/executor.py

Requirements:
- Uses LangChain create_react_agent with 3 tools: web_search, arxiv_search, load_url
- Max iterations: 8 (prevent infinite tool loops)
- After tool loop: parse result into structured ExecutorOutput
- ExecutorOutput: summary (str), claims (List[ClaimDict]), sources (List[SourceDict]), confidence (float)
- Content deduplication: hash each claim text, skip if hash seen in session's Qdrant collection
- Stores new chunks in Qdrant with metadata: session_id, task_id, source_url, confidence
- Builds graph_nodes/graph_edges from found sources and concepts (for Neo4j)
- Error handling: if agent crashes, mark task as "failed", return partial results
- Async: execute() is async, uses await for Qdrant calls

For graph node extraction: prompt a separate LLM call to extract concept names from the summary.
Format: "Extract 3–5 key concepts from this text. Return JSON array of strings."

Include complete implementation. Use AsyncQdrantClient.
```

---

### P1-CDX-3 — Parallel Executor Fan-out Node

```
Generate the execute_node function for LangGraph that runs multiple executors in parallel.

The function must:
1. Find all TaskItems in state["task_graph"] with status="pending" (or status="retry")
2. Create one ExecutorAgent per task (pool from settings.EXECUTOR_POOL_SIZE)
3. Run all tasks concurrently with asyncio.gather()
4. Collect results: updated TaskItems, new sources, new graph_nodes/edges
5. Publish SSE events to Redis for each completed task:
   channel: f"session:{state['session_id']}:events"
   event: {"type": "task_update", "task_id": task.id, "status": "done", "confidence": ...}
6. Update task statuses in task_graph
7. Increment iteration_count by 1
8. Return merged state dict

Handle partial failures: if 1 of 3 executors fails, continue with the 2 that succeeded.
Log the failure with structlog, mark the task as "failed" in task_graph.

Use: asyncio.gather(*coroutines, return_exceptions=True) — check for Exception instances.
```

---

### P1-AG-1 — Antigravity: Bootstrap Entire Agent Directory

```
Antigravity Task: Create all agent files for a LangGraph research system.

Working directory: backend/agents/

Files to create in order:
1. __init__.py — export PlannerAgent, ExecutorAgent, CriticAgent, SynthesizerAgent, ContradictionEngine
2. planner.py — [See P1-CDX-1 prompt above]
3. executor.py — [See P1-CDX-2 prompt above]
4. critic.py — CriticAgent.critique(state) → CriticOutput
5. synthesizer.py — SynthesizerAgent.synthesize(state) → {synthesis: str}
6. contradiction_engine.py — ContradictionEngine.detect(state) → {contradictions: [...]}

For each file:
- After creating: run `python -c "from backend.agents.X import X; print('OK')"` to verify imports
- If import fails: fix the error before proceeding to next file
- After all files: run `python -m pytest tests/unit/test_agents.py -v`

Stop and report if any file fails import after 2 fix attempts.
```

---

## PHASE 2: Memory & Knowledge Graph

### P2-CL-1 — Neo4j Schema Design

```
You are a graph database architect.

I am building a real-time knowledge graph for a multi-agent research system.
The system produces: concepts, claims, sources, contradictions, sessions.

Design the complete Neo4j schema:
1. Node labels with exact properties (include data types)
2. Relationship types with direction and properties
3. Indexes needed for performance (which properties?)
4. Constraints (uniqueness, existence)
5. The Cypher patterns for:
   a. "Find all claims that contradict claims related to concept X"
   b. "Get the full evidence chain for claim Y (claim → source → supporting claims)"
   c. "Cross-session: find concepts seen in >2 sessions" (for memory continuity)

Also: should I use Neo4j 5's vector search indexes to store embeddings in Neo4j instead of 
Qdrant separately? What are the tradeoffs? Be specific about Neo4j vector index limitations
vs Qdrant's capabilities.
```

---

### P2-CL-2 — Contradiction Classification Strategy

```
I am building a contradiction detection engine for a multi-agent research system.

The engine must classify contradictions into 3 types:
- direct: Same question, opposite factual answers ("accuracy is 94%" vs "accuracy is 78%")
- methodological: Different research methods on same question reach opposite conclusions
- scope: Claims are true in different scopes but presented as universal

Questions:
1. What is the optimal retrieval strategy to find candidate contradiction pairs among N claims?
   (I have embedding vectors for all claims)
2. What cosine similarity threshold should I use to identify "potentially contradicting" pairs?
3. How do I design the LLM prompt to distinguish methodological vs scope contradictions?
   Give me the exact prompt.
4. What severity scoring rubric makes sense for each contradiction type?
5. How should the Synthesizer handle each type differently in the final report?

Be specific. Give examples from the research domain.
```

---

### P2-CDX-1 — Neo4j Knowledge Graph Client

```
Generate `backend/memory/knowledge_graph.py`.

Complete Neo4j client for a research knowledge graph.

Class: KnowledgeGraphClient
__init__(self, uri, user, password): 
  - Use neo4j.AsyncGraphDatabase.driver
  - On init: run schema setup (constraints + indexes)

async setup_schema(self):
  Run these Cypher statements:
  - CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE
  - CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (c:Claim) REQUIRE c.id IS UNIQUE
  - CREATE CONSTRAINT source_id IF NOT EXISTS FOR (s:Source) REQUIRE s.id IS UNIQUE
  - CREATE INDEX concept_name IF NOT EXISTS FOR (c:Concept) ON (c.name)
  - CREATE FULLTEXT INDEX claim_text IF NOT EXISTS FOR (c:Claim) ON EACH [c.text]

async upsert_concept(name: str, description: str, session_id: str) -> str:
  - MERGE by normalized name (lowercase, stripped)
  - Return concept id

async add_claim(text: str, source_ids: List[str], concept_ids: List[str], 
                task_id: str, session_id: str, confidence: float) -> str:
  - CREATE claim node
  - CREATE [:SUPPORTED_BY] to each source
  - CREATE [:RELATES_TO] to each concept
  - Return claim id

async add_contradiction(claim_a_id: str, claim_b_id: str, 
                        type: str, severity: float, explanation: str) -> str:
  - CREATE contradiction node
  - CREATE [:INVOLVES] edges to both claims
  - CREATE [:CONTRADICTS] edge between the two claims (bidirectional)

async get_graph_snapshot(session_id: str) -> dict:
  - Query all nodes and relationships for session
  - Return {"nodes": [...], "edges": [...]} D3-compatible format
  - Node format: {id, label, type, confidence, properties}
  - Edge format: {source, target, type, properties}

async close(self): close driver

Handle Neo4j connection errors with retry (3 attempts). Use async sessions.
```

---

### P2-CDX-2 — Qdrant Vector Store

```
Generate `backend/memory/vector_store.py`.

Class: VectorMemory
__init__(self, host, port, collection_name="research_memory"):
  - AsyncQdrantClient
  - On init: create collection if not exists
    - vectors: size=1536, distance=Cosine
    - payload indexes: session_id (keyword), source_type (keyword)

async upsert_chunks(chunks: List[str], metadata_list: List[dict]):
  - Get embeddings via OpenAI ada-002 (batch, max 100 per call)
  - For each chunk: compute sha256 hash
  - Check existing: search by hash in payload filter (exact match)
  - Only upsert chunks with new hashes
  - PointStruct: id=uuid5(hash), vector=embedding, payload=metadata+hash

async semantic_search(query: str, session_id: Optional[str] = None, 
                      top_k: int = 10) -> List[dict]:
  - Embed query
  - QdrantFilter: must=[FieldCondition(session_id)] if session_id given
  - Search with score_threshold=0.7
  - Return: [{text, score, metadata}]

async mmr_search(query: str, session_id: str, top_k: int = 10, 
                 lambda_mult: float = 0.5) -> List[dict]:
  - Fetch top 30 candidates
  - Apply MMR algorithm: iteratively select candidates that maximize
    relevance to query AND minimize similarity to already-selected items
  - Return top_k results

async get_session_summary(session_id: str) -> str:
  - Retrieve all chunks for session
  - Return concatenated text (first 3000 tokens)

Use openai.AsyncOpenAI for embeddings. Handle rate limits with tenacity retry.
```

---

### P2-AG-1 — Antigravity: Wire Memory into Agents

```
Antigravity Task: Update executor.py and planner.py to use the memory systems.

Steps:
1. Read current backend/agents/executor.py
2. Import VectorMemory and KnowledgeGraphClient
3. Add to ExecutorAgent.__init__: accept vector_memory and kg_client parameters
4. In execute() method, after getting results:
   a. Call vector_memory.upsert_chunks(claims_as_text, metadata)
   b. Call kg_client.add_claim() for each extracted claim
   c. Call kg_client.upsert_concept() for each extracted concept
5. Read current backend/agents/planner.py
6. Add to plan() method at the start:
   a. Call vector_memory.semantic_search(query, top_k=5) for prior context
   b. If results found: add "Prior research context:" section to prompt
7. Update backend/graph/workflow.py to pass memory clients to all agents
8. Run: python scripts/integration_test.py --query "test memory integration"
9. Verify: check Neo4j browser at http://localhost:7474 for nodes
10. Report: node count and relationship count after test run
```

---

## PHASE 3: API + Streaming

### P3-CL-1 — SSE Architecture Decision

```
I need to implement Server-Sent Events (SSE) for a research AI system where:
- Agent runs async in background (LangGraph graph.invoke() in asyncio task)
- Frontend subscribes to live updates during 60–300 second research sessions
- System runs on ECS with multiple backend pods behind an ALB
- Need: task updates, graph updates, contradiction alerts, final synthesis

Design decision: Which pub/sub transport should I use?

Options:
A) In-memory asyncio.Queue (simple, per-process)
B) Redis pub/sub (cross-process, with AsyncRedis)
C) PostgreSQL LISTEN/NOTIFY
D) AWS EventBridge

Evaluate against:
- Multi-pod ECS deployment (client could reconnect to different pod)
- 100 concurrent research sessions
- Message delivery guarantee requirements
- Reconnection with Last-Event-ID

Recommend one. Give exact Redis pub/sub implementation pattern for:
1. Agent publishes event
2. SSE endpoint subscribes and streams

Include the exact Python asyncio + aioredis code pattern.
```

---

### P3-CDX-1 — SSE Streaming Endpoint

```
Generate `backend/api/routes/stream.py`.

FastAPI SSE streaming endpoint:

GET /api/v1/stream/{session_id}
- Returns StreamingResponse(media_type="text/event-stream")
- Sets headers: Cache-Control: no-cache, X-Accel-Buffering: no (for nginx)
- Generator function (async):
  1. Connect to Redis: subscribe to channel f"session:{session_id}:events"
  2. Loop:
     - Wait for message with timeout=15s
     - If timeout: yield heartbeat: f"data: {json.dumps({'type':'heartbeat'})}\n\n"
     - If message: parse JSON, add id (auto-incrementing), yield SSE
       Format: f"id: {event_id}\ndata: {json.dumps(event)}\n\n"
     - If message type is "synthesis_complete": yield final event, break loop
  3. On client disconnect (GeneratorExit): unsubscribe from Redis, cleanup
  4. On Redis error: yield error event, retry connection once

Also implement: _publish_event(session_id: str, event: dict) helper function
that agents call to publish to Redis. Export this helper.

Event ID tracking: use Redis INCR on key f"session:{session_id}:event_counter" for IDs.
Client reconnection: read Last-Event-ID header, replay missed events from Redis stream
(use Redis XREAD with stream key f"session:{session_id}:stream" for persistence).

Include imports. Use aioredis (not deprecated redis.asyncio directly).
```

---

### P3-CDX-2 — HITL Interrupt/Resume

```
Generate `backend/api/routes/control.py`.

Two endpoints for Human-In-The-Loop control:

POST /api/v1/interrupt/{session_id}
Body: InterruptRequest(reason: str)
Logic:
1. Load current checkpoint from LangGraph PostgresSaver using session_id as thread_id
2. If no checkpoint: raise 404
3. If state["interrupt_requested"] already True: raise 409 (already interrupted)
4. Update state: interrupt_requested=True, metadata.interrupt_reason=reason
5. Save updated checkpoint
6. Publish SSE event: {"type": "interrupt_requested", "reason": reason}
7. Return: {"status": "interrupted", "session_id": session_id}

POST /api/v1/resume/{session_id}
Body: ResumeRequest(feedback: str, action: Literal["continue", "replan", "abort"])
Logic:
1. Load checkpoint
2. If not interrupted: raise 409
3. If action == "abort": publish synthesis_complete with partial results, return
4. Update state: 
   - interrupt_requested=False
   - human_feedback=feedback
   - if action=="replan": set task_graph back to [] (force replan)
5. Re-invoke graph: await graph.ainvoke(None, config={"configurable": {"thread_id": session_id}})
   (passing None resumes from checkpointed state)
6. Return: {"status": "resumed", "action": action}

Access compiled_graph via app.state.graph (set during lifespan).
```

---

## PHASE 4: Frontend

### P4-CL-1 — D3 Graph vs React-Force-Graph Tradeoff

```
I need to render a live knowledge graph in my Next.js frontend.

Options:
A) Pure D3 force simulation in useEffect
B) react-force-graph library (wraps D3)
C) Cytoscape.js
D) Sigma.js

Requirements:
- Nodes arrive incrementally via SSE (not batch)
- 4 node types, 3 edge types with different styles
- Click handlers on nodes
- Contradiction edges must pulse/animate
- Must handle 200+ nodes without performance issues
- No SSR issues (runs client-side only)

For each option: performance characteristics at 200 nodes, SSR compatibility,
incremental update pattern (add node without full redraw).

Recommend one. For D3: explain the exact useEffect cleanup pattern for React 18
strict mode (double-invoke issue). Give the pattern for incrementally adding nodes
to an existing simulation without restarting it.
```

---

### P4-CDX-1 — D3 Knowledge Graph Component

```
Generate `frontend/components/KnowledgeGraph.tsx`.

React component with D3 force-directed graph:

interface Props {
  nodes: GraphNode[]
  edges: GraphEdge[]
  onNodeClick: (node: GraphNode) => void
}

interface GraphNode {
  id: string
  label: string
  type: "concept" | "claim" | "source" | "contradiction"
  confidence: number
}

interface GraphEdge {
  source: string
  target: string
  type: "relates_to" | "supports" | "contradicts"
}

Implementation requirements:
- "use client" directive
- useRef<SVGSVGElement>(null) for SVG mount point
- Separate useRef for D3 simulation (persist across renders)
- useEffect for D3 init (empty deps — run once)
- useEffect for data updates (deps: [nodes, edges]) — add/update nodes incrementally:
  simulation.nodes(nodes); simulation.force("link").links(edges); simulation.alpha(0.3).restart()
  Do NOT reinitialize simulation on every update.

Styles:
- concept: fill #3B82F6, r=10
- claim: fill #10B981, r=8  
- source: fill #6B7280, r=6
- contradiction: fill #EF4444, r=10
- Node opacity = 0.6 + (0.4 * confidence)

Edges:
- contradicts: stroke #EF4444, strokeDasharray "5,5", strokeWidth 2
  add CSS animation: @keyframes dash { to { stroke-dashoffset: -10 } }
- supports: stroke #9CA3AF, strokeWidth 1
- relates_to: stroke #3B82F6, strokeWidth 1.5

Tooltip: floating div (not SVG), positioned at mouse, shown on mouseover node.
Shows: label, type, confidence percentage.

Cleanup: return () => { simulation.stop() } from init useEffect.
Width/height: use ResizeObserver on container div.

Full TypeScript. No any types. Export as default.
```

---

### P4-AG-1 — Antigravity: Full Frontend Build

```
Antigravity Task: Build the complete Next.js frontend for the Research Intelligence Platform.

Step 1: Setup
  - Run: npx create-next-app@latest frontend --typescript --tailwind --app --no-src-dir
  - cd frontend && npm install d3 @types/d3 zustand framer-motion

Step 2: Create files in this order:
  a. frontend/lib/types.ts — All TypeScript interfaces
  b. frontend/lib/api.ts — API client functions
  c. frontend/hooks/useSSE.ts — SSE hook
  d. frontend/store/research.ts — Zustand store for research state
  e. frontend/components/QueryInput.tsx
  f. frontend/components/AgentTimeline.tsx
  g. frontend/components/KnowledgeGraph.tsx
  h. frontend/components/ContradictionPanel.tsx
  i. frontend/components/SynthesisReport.tsx
  j. frontend/components/HITLModal.tsx
  k. frontend/app/page.tsx
  l. frontend/app/research/[sessionId]/page.tsx

Step 3: After each component, run: npx tsc --noEmit
  If TypeScript errors: fix before proceeding.

Step 4: Run: npm run dev
  Test: open http://localhost:3000, submit a query, verify redirect to /research/{id}

Step 5: Run: npm run build
  Fix any build errors.

Report file count, TypeScript error count (target: 0), and build success/failure.
```
