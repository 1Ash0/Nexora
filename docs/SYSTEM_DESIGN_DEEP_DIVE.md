# SYSTEM_DESIGN_DEEP_DIVE.md
# Research Intelligence Platform — Full Architecture

---

## System Overview

The Research Intelligence Platform (RIP) is an event-driven, multi-agent AI system where autonomous agents collaboratively conduct research, build a live knowledge graph, detect contradictions, and synthesize findings — with human-in-the-loop control at any point.

---

## High-Level Architecture (ASCII)

```
┌────────────────────────────────────────────────────────────────────────────┐
│                           CLIENT LAYER                                      │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │  Next.js Frontend                                                    │  │
│   │  ┌─────────────┐  ┌───────────────┐  ┌──────────────────────────┐  │  │
│   │  │ Query Input  │  │ Agent Timeline │  │  D3 Knowledge Graph       │  │
│   │  └──────┬──────┘  └──────┬────────┘  └────────────┬─────────────┘  │  │
│   │         │  (REST)         │  (SSE)                  │  (REST poll)   │  │
│   └─────────┼─────────────────┼─────────────────────────┼───────────────┘  │
└─────────────┼─────────────────┼─────────────────────────┼──────────────────┘
              ↓                 ↓                          ↓
┌────────────────────────────────────────────────────────────────────────────┐
│                           API GATEWAY LAYER                                  │
│   ┌──────────────────────────────────────────────────────────────────────┐  │
│   │  FastAPI (uvicorn, async)                                             │  │
│   │  POST /research  │  GET /stream/{id} (SSE)  │  POST /interrupt/resume │  │
│   └────────┬─────────┴────────────┬─────────────┴─────────────────────────┘  │
└────────────┼────────────────────┼──────────────────────────────────────────┘
             ↓                    ↓
┌────────────────────────────────────────────────────────────────────────────┐
│                     ORCHESTRATION LAYER (LangGraph)                          │
│                                                                              │
│   ┌──────────┐    ┌─────────────────────────┐    ┌──────────┐              │
│   │          │    │   EXECUTOR POOL          │    │          │              │
│   │ PLANNER  │───▶│  Executor-1              │───▶│ CONTRA-  │              │
│   │  Agent   │    │  Executor-2  (parallel)  │    │ DICTION  │              │
│   │          │    │  Executor-3              │    │ ENGINE   │              │
│   └──────────┘    └─────────────────────────┘    └────┬─────┘              │
│        ▲                                               │                     │
│        │  replan                                       ↓                     │
│   ┌────┴─────┐                                   ┌──────────┐              │
│   │          │◀──────────────────────────────────│  CRITIC  │              │
│   │          │  retry                            │  Agent   │              │
│   │          │                                   └────┬─────┘              │
│   │          │                                        │ pass               │
│   │          │                                        ↓                     │
│   │          │                                   ┌──────────┐              │
│   │          │                                   │SYNTHESI- │              │
│   │          │                                   │  ZER     │───▶ END      │
│   │          │                                   └──────────┘              │
│   │  HITL    │                                                              │
│   │ INTERRUPT│◀─────────────── Optional interrupt point ──────────────────│
│   └──────────┘                                                              │
└────────────────────────────────────────────────────────────────────────────┘
             │ reads/writes                │ reads/writes
             ↓                            ↓
┌──────────────────────┐    ┌──────────────────────────────────────────────┐
│   MEMORY LAYER        │    │   PERSISTENCE LAYER                           │
│  ┌────────────────┐  │    │  ┌──────────────┐  ┌────────┐  ┌─────────┐  │
│  │  Qdrant        │  │    │  │ PostgreSQL   │  │ Redis  │  │  Neo4j  │  │
│  │  Vector Store  │  │    │  │ (LangGraph   │  │ (SSE   │  │  (Know- │  │
│  │  (semantic     │  │    │  │  checkpoint) │  │  pub/  │  │  ledge  │  │
│  │   dedup,       │  │    │  │              │  │  sub)  │  │  Graph) │  │
│  │   retrieval)   │  │    │  └──────────────┘  └────────┘  └─────────┘  │
│  └────────────────┘  │    └──────────────────────────────────────────────┘
└──────────────────────┘
```

---

## Data Flow: Single Research Session

### Phase 1: Query → Task Graph

```
User types query: "Compare RAG vs fine-tuning for domain adaptation"
         │
         ▼
POST /api/v1/research
  - Generates session_id (UUID4)
  - Creates ResearchState (initial)
  - Spawns asyncio background task: graph.ainvoke(state, config)
  - Returns: {session_id, status: "started"}
         │
         ▼ (background)
plan_node()
  - PlannerAgent.plan(state)
  - LLM call (gpt-4o, temp=0, structured output)
  - Returns: 5 TaskItems with dependencies
  - State update: task_graph=[...], refined_query="..."
  - Publishes SSE: {type: "agent_step", agent: "planner", tasks: 5}
```

### Phase 2: Parallel Execution

```
execute_node()
  - Finds all pending tasks in task_graph
  - Creates 3 ExecutorAgents (pool)
  - asyncio.gather(exec1.execute(t1,s), exec2.execute(t2,s), exec3.execute(t3,s))
  
  Each executor runs concurrently:
  ┌─────────────────────────────────────────────────────────┐
  │ ExecutorAgent.execute(task, state)                       │
  │   1. Run LangChain ReAct agent loop (max 8 steps)       │
  │   2. Tools called: web_search → load_url → arxiv_search │
  │   3. Extract claims + sources from final answer          │
  │   4. Hash claims → check Qdrant for duplicates           │
  │   5. Upsert new chunks to Qdrant                         │
  │   6. Extract concepts via LLM call                       │
  │   7. Write to Neo4j: concepts, claims, sources           │
  │   8. Return: TaskItem(status=done, result, confidence)   │
  │   9. Publish SSE: {type: "task_update", ...}             │
  └─────────────────────────────────────────────────────────┘
  
  State merge (LangGraph handles):
    completed_tasks += [result1, result2, result3]  (Annotated add)
    sources += [sources1, sources2, sources3]        (Annotated add)
    graph_nodes += [nodes1, nodes2, nodes3]          (Annotated add)
```

### Phase 3: Contradiction Detection

```
contradiction_node()
  - All claims from completed_tasks extracted
  - Batch embed all claims: OpenAI ada-002 (single API call)
  - Build similarity matrix: O(n²) cosine similarities
  - Filter pairs: cosine > 0.75 (same topic threshold)
  - For each candidate pair: LLM call to classify
  - Write contradictions to Neo4j (CONTRADICTS edges)
  - Publish SSE: {type: "contradiction_found", ...} for each
  - State update: contradictions += [...]
```

### Phase 4: Critic Evaluation + Routing

```
critique_node()
  - Assembles all task results into critic context
  - LLM call: evaluate coverage, accuracy, depth
  - Returns CriticOutput with verdict

route_critique() conditional edge:
  ├── verdict == "pass" AND interrupt_requested == False → synthesize_node
  ├── verdict == "pass" AND interrupt_requested == True → human_feedback_node (INTERRUPT)
  ├── verdict == "replan" AND iteration < 3 → plan_node (iteration += 1)
  └── verdict == "retry" → execute_node (only failed tasks re-run)
```

### Phase 5: Synthesis

```
synthesize_node()
  - Collects: all task results, all contradictions, all sources
  - Truncates to 8000 tokens (most confident chunks first)
  - LLM call (gpt-4o, temp=0.3)
  - Output: structured research report (2000–4000 words)
  - State update: synthesis = "..."
  - Publish SSE: {type: "synthesis_complete", report: "..."}
  - Graph: END
```

---

## Agent Loop Lifecycle

```
State machine per session:

CREATED
  │ (graph.ainvoke called)
  ▼
PLANNING
  │ (plan_node completes)
  ▼
EXECUTING ──────────────────────────────────────────────────────────────┐
  │ (all executors complete)                                             │
  ▼                                                                      │
DETECTING_CONTRADICTIONS                                                  │
  │                                                                      │
  ▼                                                                      │
CRITIQUING                                                                │
  │                                                                      │
  ├── [replan, iter < 3] ──▶ PLANNING (loop back)                       │
  │                                                                      │
  ├── [retry] ──────────────────────────────────────────────────────────┘
  │
  ├── [pass, interrupt] ──▶ INTERRUPTED
  │                               │
  │                               │ (POST /resume)
  │                               ▼
  │                          PLANNING (with human feedback)
  │
  └── [pass, no interrupt] ──▶ SYNTHESIZING
                                      │
                                      ▼
                                 COMPLETED
```

---

## Memory Architecture

### Three-Layer Memory Model

```
Layer 1: Short-term (within session)
  - Lives in ResearchState (LangGraph)
  - task_graph, completed_tasks, contradictions
  - Persisted to PostgreSQL via checkpointer
  - Accessible to all agents in same graph invocation

Layer 2: Mid-term (semantic, cross-session)
  - Lives in Qdrant
  - Chunked text with embeddings + session metadata
  - Queryable by: semantic similarity, session_id, source_type
  - Used by: PlannerAgent (prior context injection), ExecutorAgent (dedup)

Layer 3: Long-term (structured, persistent)
  - Lives in Neo4j
  - Concepts, claims, relationships survive session cleanup
  - Cross-session concept merging via MERGE on normalized concept name
  - Used by: contradiction detection, synthesis, multi-session continuity
```

### Memory Access Patterns Per Agent

| Agent | Reads | Writes |
|---|---|---|
| Planner | Qdrant: prior session summary | — |
| Executor | Qdrant: dedup check | Qdrant: new chunks; Neo4j: concepts, claims, sources |
| ContradictionEngine | ResearchState: all claims | Neo4j: CONTRADICTS edges; ResearchState: contradictions |
| Critic | ResearchState: all tasks | ResearchState: critic verdict |
| Synthesizer | ResearchState: everything | ResearchState: synthesis |

---

## SSE Event System

### Event Bus Architecture

```
Agent Action
    │
    │ redis.publish(f"session:{session_id}:events", json.dumps(event))
    ▼
Redis Pub/Sub
    │
    │ subscribe(channel)
    ▼
FastAPI SSE Generator
    │
    │ yield f"id: {n}\ndata: {json.dumps(event)}\n\n"
    ▼
Browser EventSource
    │
    │ event listener per type
    ▼
Zustand Store Update
    │
    ▼
React re-render (AgentTimeline, KnowledgeGraph, etc.)
```

### Complete Event Schema

```typescript
type SSEEvent =
  | { type: "agent_step"; agent: string; action: string; duration_ms: number }
  | { type: "task_update"; task_id: string; status: TaskStatus; confidence: number }
  | { type: "graph_update"; nodes: GraphNode[]; edges: GraphEdge[] }
  | { type: "contradiction_found"; contradiction: Contradiction }
  | { type: "interrupt_requested"; reason: string; options: string[] }
  | { type: "critic_result"; verdict: string; score: number; missing: string[] }
  | { type: "synthesis_complete"; report: string; word_count: number }
  | { type: "error"; message: string; recoverable: boolean }
  | { type: "heartbeat" }
```

---

## Scaling Path: V1 → V2 → V3

### V1 (Current MVP)

```
Scale: 1–10 concurrent sessions
Compute: 2 ECS tasks (2 vCPU / 4GB each)
State: Single PostgreSQL, single Redis, single Neo4j Aura
Executors: 3 per session (sequential within pool, parallel across sessions)
Cost: ~$200/month (ECS + RDS + ElastiCache + Neo4j Aura free tier)
Bottleneck: OpenAI API rate limits (~500 RPM for GPT-4o)
```

### V2 (Growth Scale)

```
Scale: 10–100 concurrent sessions
Changes:
  - ECS auto-scaling: 2–20 tasks, CPU-based
  - Redis Cluster mode: 3 shards (shard by session_id hash)
  - Neo4j Enterprise: causal cluster (3 nodes)
  - Qdrant: distributed mode (3 replicas)
  - Separate ECS task per executor agent (true microservice isolation)
  - Add: request queue (SQS) between API and agent workers
    - Decouples API latency from agent execution time
  - Add: OpenAI API rate limiter (token bucket per tenant)
Cost: ~$2,000/month
Bottleneck: Neo4j write throughput for high-claim volumes
```

### V3 (Platform Scale)

```
Scale: 100+ concurrent sessions, multi-tenant
Changes:
  - Kubernetes (EKS) replacing ECS for finer scheduling control
  - Per-tenant Neo4j database isolation (Neo4j multi-database)
  - Qdrant: per-tenant collections with quota enforcement
  - Add: async task queue (Celery/Kafka) for long-running research jobs
  - Add: LLM abstraction layer (support Claude, Gemini as fallback)
  - Add: GraphQL API for complex frontend queries
  - Add: streaming synthesis (token-by-token SSE from LLM)
  - Add: research result caching (Redis) for identical queries
Cost: ~$10,000+/month
```

---

## Key Engineering Decisions (with rationale)

### Decision 1: LangGraph over custom orchestrator

**Chosen:** LangGraph `StateGraph`
**Rejected:** Custom Python async orchestrator

**Rationale:**
- PostgreSQL checkpointing for HITL is built-in — implementing this custom requires distributed locking, state serialization, and resumption logic (weeks of work)
- Typed state with `Annotated` merging handles parallel executor output correctly
- Graph visualization of agent flow is trivially exportable from LangGraph's `get_graph()` method
- Community + Anthropic-maintained — production hardened

**Tradeoff accepted:** LangGraph adds ~50ms overhead per node transition (serialization to PostgreSQL). For our 60–300s research sessions, this is negligible.

---

### Decision 2: Redis pub/sub for SSE (not in-memory queue)

**Chosen:** Redis pub/sub per session channel
**Rejected:** asyncio.Queue in FastAPI process

**Rationale:** ECS runs multiple backend pods. A reconnecting SSE client might land on a pod that didn't start the agent. Redis decouples the event publisher (agent worker) from the event consumer (SSE endpoint). Any pod can serve any session's stream.

**Tradeoff accepted:** Adds Redis as a required dependency. Adds ~1–2ms latency per event (Redis RTT). Both acceptable.

---

### Decision 3: Neo4j + Qdrant (not single vector DB)

**Chosen:** Neo4j for graph + Qdrant for vectors
**Rejected:** Neo4j 5 vector indexes for both

**Rationale:**
- Neo4j vector indexes support up to 4096 dimensions but are optimized for exact match, not approximate nearest neighbor at scale
- Qdrant's HNSW index handles 1M+ vectors at <10ms P99, which Neo4j's vector index cannot match
- Graph traversal (find contradictions within 2 hops of concept X) is impossible in Qdrant
- Each system does one thing extremely well — composing them is the correct pattern

**Tradeoff accepted:** Two databases to operate, maintain, and pay for. Justified by the qualitative difference in capability.

---

### Decision 4: Three-class contradiction taxonomy

**Chosen:** direct | methodological | scope
**Rejected:** Binary (contradicts / doesn't contradict)

**Rationale:** How the synthesizer handles a contradiction depends entirely on its type:
- `direct`: One source is likely wrong. Synthesizer should note the discrepancy and weight by source credibility.
- `methodological`: Both may be correct. Synthesizer should explain why methods diverge.
- `scope`: Both are correct in their respective domains. Synthesizer should clarify scope boundaries.

Binary contradiction detection produces a contradiction alert with no actionable guidance. Three-class classification changes the synthesis strategy.

---

## Failure Modes and Mitigations

| Failure | Detection | Mitigation |
|---|---|---|
| OpenAI API timeout | Executor returns `ToolError` after 3 retries | Mark task `failed`, continue with remaining tasks, lower session confidence |
| Neo4j connection lost | Health check in API startup + per-request retry | Exponential backoff (1s, 2s, 4s), circuit breaker after 10 failures |
| Infinite replan loop | `iteration_count` check in `route_critique` | Force `pass` after `MAX_ITERATIONS` (default 3) |
| Executor returns empty result | `confidence == 0.0` check | Critic scores low → retry; if persistent, mark as low-confidence finding |
| SSE client disconnect | `GeneratorExit` caught in generator | Unsubscribe from Redis, log session client_disconnected |
| PostgreSQL checkpoint failure | LangGraph raises `CheckpointerError` | Log + alert; session continues in-memory, cannot resume after pod restart |
| Redis pub/sub message loss | No guaranteed delivery in pub/sub | Agents also write to Redis Stream (XADD); SSE endpoint reads from stream with XREAD for reconnection |
