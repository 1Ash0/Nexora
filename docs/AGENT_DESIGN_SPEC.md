# AGENT_DESIGN_SPEC.md
# Complete Agent Design Specification

---

## Agent Overview

| Agent | Role | LLM Calls per Session | Parallel |
|---|---|---|---|
| PlannerAgent | Decomposes query into task DAG | 1–3 (+ retries) | No (sequential) |
| ExecutorAgent | Runs tools, retrieves information | 5–15 (ReAct loop) | Yes (3 concurrent) |
| CriticAgent | Evaluates research quality | 1 per iteration | No |
| ContradictionEngine | Detects claim conflicts | 1 + N pairs | No |
| SynthesizerAgent | Produces final report | 1 | No |

---

## 1. PlannerAgent

### Purpose
Given a raw user query, produce a validated directed acyclic graph of research tasks that can be executed in parallel by the executor pool.

### Input Schema
```python
class PlannerInput(BaseModel):
    original_query: str
    iteration_count: int
    human_feedback: Optional[str]       # Injected during HITL resume
    prior_context: Optional[str]        # From Qdrant: prior session summaries
    critic_missing_aspects: List[str]   # From previous iteration's CriticOutput
```

### Output Schema
```python
class PlannerOutput(BaseModel):
    refined_query: str
    tasks: List[TaskItem]
    reasoning: str       # Why this decomposition (for debugging + HITL display)
    
    @validator("tasks")
    def validate_task_count(cls, v):
        assert 3 <= len(v) <= 7, f"Expected 3–7 tasks, got {len(v)}"
        return v
    
    @validator("tasks")
    def validate_no_cycles(cls, v):
        # DFS cycle detection on dependency graph
        id_map = {t.id: t for t in v}
        visited, in_stack = set(), set()
        def dfs(nid):
            visited.add(nid); in_stack.add(nid)
            for dep in id_map.get(nid, TaskItem()).dependencies:
                if dep not in id_map: raise ValueError(f"Unknown dep: {dep}")
                if dep in in_stack: raise ValueError(f"Cycle at {nid} → {dep}")
                if dep not in visited: dfs(dep)
            in_stack.remove(nid)
        for t in v: 
            if t.id not in visited: dfs(t.id)
        return v
```

### Prompt Template
```
System: You are a research decomposition specialist for an AI research system.
        Your output will be executed by parallel research agents.

User:
Research Query: {original_query}
Iteration: {iteration_count} / 3
{feedback_block}
{prior_context_block}
{missing_aspects_block}

Decompose this query into 3–7 parallel, independently-executable research tasks.

Guidelines:
- Each task should be completable via web search + one or two targeted URLs
- Cover dimensions: background/fundamentals, current state-of-art, comparisons, 
  limitations/criticisms, applications, future directions
- Set dependencies ONLY when task B genuinely cannot start without task A's output
- Priority 1 = must-do; Priority 3 = nice-to-have
- refined_query should reframe the query for precision

Output JSON matching PlannerOutput schema exactly. No prose outside JSON.

{feedback_block template}:
Human Feedback (incorporate this): {human_feedback}

{missing_aspects_block template}:
Previous iteration missed these aspects (add tasks to cover them):
{missing_aspects joined with newlines}
```

### Failure Cases & Handling

| Failure | Detection | Recovery |
|---|---|---|
| LLM returns invalid JSON | `json.JSONDecodeError` | Retry with "Return valid JSON only" appended |
| Cycle in task graph | `ValueError` from validator | Retry with "Do not create circular dependencies" |
| < 3 tasks generated | `ValueError` from validator | Retry with "Generate at least 3 tasks" |
| LLM times out | `asyncio.TimeoutError` | Fallback: split query into 3 generic tasks via keyword extraction |
| Infinite replan | `iteration_count >= MAX_ITERATIONS` | Force `pass` verdict in Critic routing |

### Optimization Ideas
- Cache planner output for identical (query, iteration=0) pairs using Redis (TTL 1h)
- Use streaming output to show task creation in real-time on frontend
- Implement query classification to select better task templates (e.g., technical comparison vs. overview queries use different task sets)

---

## 2. ExecutorAgent

### Purpose
Given a single TaskItem, use tools to research it thoroughly, extract structured claims, and store results in memory.

### Input Schema
```python
class ExecutorInput(BaseModel):
    task: TaskItem
    original_query: str
    session_id: str
    prior_task_results: List[str]  # Summaries of completed tasks (for context)
```

### Output Schema
```python
class ExecutorOutput(BaseModel):
    task_id: str
    status: Literal["done", "failed"]
    summary: str               # 200–500 word research summary
    claims: List[ClaimDict]    # Extracted factual claims
    sources: List[SourceDict]  # All sources used
    confidence: float          # 0.0–1.0 overall confidence
    graph_nodes: List[dict]    # Concept nodes to add to Neo4j
    graph_edges: List[dict]    # Edges to add to Neo4j

class ClaimDict(TypedDict):
    text: str
    source_url: str
    confidence: float
    claim_type: str   # "fact" | "opinion" | "statistic" | "finding"

class SourceDict(TypedDict):
    url: str
    title: str
    source_type: str   # "web" | "arxiv" | "pdf"
    retrieved_at: str  # ISO8601
    credibility: float # 0.0–1.0 (estimated from domain)
```

### ReAct Agent Prompt
```
System: You are a precision research agent. Your goal is to find specific, accurate 
        information about the given research task using available tools.
        
        Research context: {original_query}

User:
Research Task: {task_description}

Previous findings from other tasks (do not duplicate):
{prior_task_results}

Instructions:
1. Start with web_search to identify key sources
2. Use load_url on the 2–3 most relevant results for full content
3. Use arxiv_search for any academic claims
4. Stop when you have 3+ independent sources or after 8 tool calls
5. Extract specific claims with their source URLs
6. Rate your confidence in the overall findings (0.0–1.0)

After your research, provide a structured summary with all findings and sources.
```

### Tool Selection Logic
```python
# Executors choose tools based on task type
def select_tools(task: TaskItem) -> List[Tool]:
    base_tools = [web_search, load_url]
    
    # Add arxiv for scientific/technical tasks
    if any(kw in task.description.lower() 
           for kw in ["paper", "study", "research", "academic", "arxiv", "published"]):
        base_tools.append(arxiv_search)
    
    return base_tools
```

### Confidence Scoring Logic
```python
def score_confidence(sources: List[SourceDict], claims: List[ClaimDict]) -> float:
    source_score = min(len(sources) / 3.0, 1.0)       # 0.0–1.0 based on source count
    credibility_score = mean([s["credibility"] for s in sources]) if sources else 0.0
    claim_agreement = _compute_claim_agreement(claims)  # How consistent are claims across sources
    
    return 0.4 * source_score + 0.4 * credibility_score + 0.2 * claim_agreement

def _estimate_credibility(url: str) -> float:
    # Domain-based heuristic
    if "arxiv.org" in url or "nature.com" in url: return 0.9
    if ".edu" in url or ".gov" in url: return 0.85
    if "wikipedia.org" in url: return 0.6
    if "medium.com" in url or "substack.com" in url: return 0.5
    return 0.65  # unknown domain default
```

### Failure Cases & Handling

| Failure | Detection | Recovery |
|---|---|---|
| Tool API timeout | `ToolError` after 3 retries | Skip tool, continue with remaining tools |
| ReAct loop hits max iterations | LangChain `StopIteration` | Return partial result with low confidence |
| No sources found | `len(sources) == 0` | Try fallback: broader web_search query (strip specifics) |
| Content extraction fails | `BeautifulSoup` returns empty | Try 2nd URL from search results |
| Qdrant connection fails | `QdrantException` | Skip storage, log warning (research continues) |

---

## 3. CriticAgent

### Purpose
Evaluate the collective output of all executors. Determine whether the research is sufficient for synthesis or requires more work.

### Input Schema
```python
class CriticInput(BaseModel):
    original_query: str
    completed_tasks: List[TaskItem]
    contradictions: List[Contradiction]
    iteration_count: int
    max_iterations: int
```

### Output Schema (reuse from state.py)
```python
class CriticOutput(BaseModel):
    verdict: Literal["pass", "replan", "retry"]
    overall_score: float       # 0.0–1.0
    coverage_score: float      # Does research address all aspects of query?
    accuracy_score: float      # Are claims supported by credible sources?
    depth_score: float         # Is analysis substantive?
    missing_aspects: List[str] # What aspects of the query are uncovered?
    retry_tasks: List[str]     # Task IDs that produced low-quality results
    new_tasks: List[TaskItem]  # Additional tasks to add (for replan)
    reasoning: str             # Critic's overall assessment
```

### Prompt Template
```
System: You are a harsh but fair academic peer reviewer.
        Evaluate research findings against the original query.
        Be demanding. Surface real gaps. Do not accept surface-level coverage.

User:
Original Research Query: {original_query}

Research Findings:
{formatted_task_summaries}

Contradictions Found: {contradiction_count}
{formatted_contradictions}

Evaluation Rubric:
1. Coverage (0–1): Does this research address ALL major aspects of the query?
   - Score < 0.6 → must replan with missing_aspects
2. Accuracy (0–1): Are claims grounded in credible, citable sources?
   - Score < 0.5 → retry low-confidence tasks
3. Depth (0–1): Are findings specific enough to be actionable?
   - "LLMs are powerful" = low depth. "GPT-4 scores 87.1% on MMLU" = high depth.

Scoring guide:
- overall ≥ 0.80: verdict = "pass"
- overall 0.60–0.79 with missing_aspects: verdict = "replan"  
- overall < 0.60 OR specific tasks failed: verdict = "retry"
- iteration ≥ max_iterations: ALWAYS verdict = "pass" (prevent infinite loop)

Output JSON matching CriticOutput. Be specific in missing_aspects and reasoning.
```

### Routing Logic (in `route_critique` edge function)
```python
def route_critique(state: ResearchState) -> str:
    verdict = state["metadata"].get("critic_verdict", "pass")
    
    if state["interrupt_requested"]:
        return "human_feedback"
    
    if state["iteration_count"] >= state["metadata"].get("max_iterations", 3):
        return "synthesize"  # Force completion — never loop forever
    
    route_map = {
        "pass": "synthesize",
        "replan": "plan",
        "retry": "execute",
    }
    return route_map.get(verdict, "synthesize")
```

---

## 4. ContradictionEngine

### Purpose
Detect, classify, and record conflicts between claims found by different executor agents.

### Algorithm

```
Step 1: Claim extraction
  - Flatten all ClaimDicts from completed_tasks
  - Result: N claims with text + source_url

Step 2: Embedding
  - Batch embed all claims: OpenAI ada-002
  - Cost: 1 API call for up to 2048 claims (batch)
  - Result: N × 1536 embedding matrix

Step 3: Candidate pair finding
  - Compute pairwise cosine similarity: O(N²)
  - N = 50 claims → 1,225 pairs (fast enough)
  - Filter: similarity > 0.75 AND different source_urls
  - Result: M candidate pairs (typically 5–30 for a research session)

Step 4: LLM classification (per candidate pair)
  - One LLM call per pair (batched for efficiency)
  - Returns: {contradicts: bool, type: str, severity: float, explanation: str}
  - Filter: contradicts == True

Step 5: Graph update
  - For each confirmed contradiction: write to Neo4j
  - Emit SSE event: {type: "contradiction_found", ...}
```

### Prompt Template (per candidate pair)
```
You are evaluating whether two research claims contradict each other.

Claim A: "{claim_a}"
Source A: {source_a}

Claim B: "{claim_b}"  
Source B: {source_b}

Analysis questions:
1. Do these claims make incompatible assertions about the same topic?
2. If yes, why do they conflict?
   - "direct": They assert opposite facts about the same thing
   - "methodological": They use different methods and reach opposite conclusions
   - "scope": One is universally stated but only true in specific conditions
3. How severe is this contradiction? (0.0 = trivial, 1.0 = fundamental)

Output JSON only:
{
  "contradicts": true/false,
  "type": "direct" | "methodological" | "scope",
  "severity": 0.0–1.0,
  "explanation": "one sentence"
}
```

### Input Schema
```python
class ContradictionInput(BaseModel):
    claims: List[ClaimDict]
    session_id: str
```

### Output Schema
```python
class ContradictionOutput(BaseModel):
    contradictions: List[Contradiction]
    candidate_pairs_evaluated: int
    contradictions_found: int
    graph_edges: List[dict]   # {source: claim_id, target: claim_id, type: "CONTRADICTS", severity}
```

### Performance Optimization
```python
# For large claim sets, sample instead of exhaustive O(N²)
MAX_PAIRS = 500

def find_candidate_pairs(embeddings, threshold=0.75):
    similarities = cosine_similarity(embeddings)
    pairs = []
    for i in range(len(embeddings)):
        for j in range(i+1, len(embeddings)):
            if similarities[i][j] > threshold:
                pairs.append((i, j, similarities[i][j]))
    
    # Sort by similarity descending, take top MAX_PAIRS
    pairs.sort(key=lambda x: -x[2])
    return pairs[:MAX_PAIRS]
```

### Failure Cases

| Failure | Recovery |
|---|---|
| No claims from executors | Return empty contradictions (valid state) |
| Embedding API fails | Skip contradiction detection, log warning |
| All pairs below threshold | Return empty (no candidates found — valid) |
| LLM classifies incorrectly | Accepted — LLM classification has ~85% accuracy; false positives shown to user with severity score |

---

## 5. SynthesizerAgent

### Purpose
Integrate all research findings, contradictions, and source material into a comprehensive, structured research report.

### Input Schema
```python
class SynthesizerInput(BaseModel):
    original_query: str
    refined_query: str
    completed_tasks: List[TaskItem]
    contradictions: List[Contradiction]
    sources: List[SourceDict]
    human_feedback: Optional[str]
    session_id: str
```

### Output Schema
```python
class SynthesizerOutput(BaseModel):
    synthesis: str          # Full markdown report
    word_count: int
    source_count: int
    confidence_summary: str # e.g., "High confidence on X, low on Y"
    key_findings: List[str] # 3–5 bullet points for quick consumption
```

### Context Window Management
```python
def build_synthesis_context(state: ResearchState, max_tokens: int = 8000) -> str:
    parts = []
    token_budget = max_tokens
    
    # Always include: query + contradictions (small, high value)
    parts.append(f"Query: {state['refined_query']}")
    contradiction_text = format_contradictions(state['contradictions'])
    parts.append(contradiction_text)
    token_budget -= estimate_tokens(contradiction_text) + 100
    
    # Add task results: highest confidence first, until budget exhausted
    tasks_by_confidence = sorted(
        state['completed_tasks'], 
        key=lambda t: t.get('confidence', 0), 
        reverse=True
    )
    
    for task in tasks_by_confidence:
        task_text = f"Task: {task['description']}\nResult: {task['result']}"
        cost = estimate_tokens(task_text)
        if cost > token_budget: break
        parts.append(task_text)
        token_budget -= cost
    
    return "\n\n---\n\n".join(parts)
```

### Report Structure Prompt
```
System: You are a senior research analyst. Synthesize research findings into a 
        comprehensive, accurate, and useful research report.

User:
{synthesis_context}

{human_feedback_block if present}

Write a research report with this exact structure:

## Executive Summary
(2–3 paragraphs. What is the core answer to the query? What are the most important findings?)

## Key Findings
(5–8 specific, evidence-backed findings. Each must cite a source. Be specific — no vague claims.)

## Analysis
(Deep dive into the most important aspects. Compare competing approaches if relevant.
 Address all contradictions found — explain each one using its type: direct/methodological/scope.)

## Limitations and Gaps
(What did the research NOT find? What would require additional investigation?)

## Confidence Assessment
(Overall confidence level. Which findings are high-confidence vs. uncertain? Why?)

## Sources
(List all sources used. Format: [Title](URL) — relevance note)

Rules:
- Every claim in Key Findings must cite a source
- Contradictions MUST be addressed (not ignored)
- No fabricated statistics or sources
- Length: 1500–3000 words
- Use markdown formatting
```

### Failure Cases

| Failure | Recovery |
|---|---|
| Context too large | Truncate by confidence score (best tasks first) |
| LLM produces no synthesis | Return partial synthesis from task results concatenated |
| All tasks failed | Return "Research incomplete" with explanation of failure |

---

## Inter-Agent Communication Protocol

All agents communicate through `ResearchState` — no direct agent-to-agent calls. This is enforced by LangGraph's node architecture.

```
Agent writes → ResearchState → Next agent reads

Never:
  PlannerAgent.call(ExecutorAgent)  # WRONG — direct coupling
  
Always:
  plan_node() → returns state_update_dict
  LangGraph merges → state
  execute_node() reads state → runs executors
```

This enables:
- Checkpoint any intermediate state
- Replay any agent from its inputs
- Unit test any agent by constructing state directly

---

## Shared Agent Infrastructure

```python
# backend/agents/base.py
class BaseAgent:
    def __init__(self, llm: ChatOpenAI, settings: Settings):
        self.llm = llm
        self.settings = settings
        self.logger = structlog.get_logger().bind(agent=self.__class__.__name__)
    
    async def _call_llm_structured(self, prompt: str, output_schema: Type[BaseModel]) -> BaseModel:
        """LLM call with structured output, retry, and logging."""
        structured_llm = self.llm.with_structured_output(output_schema)
        
        for attempt in range(3):
            try:
                start = time.monotonic()
                result = await structured_llm.ainvoke(prompt)
                self.logger.info("llm_call_success", 
                                 attempt=attempt,
                                 duration_ms=int((time.monotonic()-start)*1000))
                return result
            except Exception as e:
                self.logger.warning("llm_call_failed", attempt=attempt, error=str(e))
                if attempt == 2: raise
                await asyncio.sleep(2 ** attempt)
```
