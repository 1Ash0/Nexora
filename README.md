# Nexora

**A transparent, multi-agent research pipeline. Every claim sourced. Every contradiction surfaced. Nothing hidden.**

Most AI research tools give you a polished answer and ask you to trust it. Nexora shows you exactly how it got there — every agent, every source, every conflict, in real time.

---

## What it looks like

> *Research query → parallel agent pipeline → structured brief with inline citations, contradiction cards, confidence score, and inline Q&A*

The frontend streams every step live. You watch the planner decompose your query, executors pull sources in parallel, the critic score confidence, and the synthesizer write the final brief — all before the report lands.

---

## Architecture

```
Query
  └── Planner          rewrites query, decomposes into 2–5 parallel tasks
        └── Executor   parallel web search + Qdrant semantic search per task
              └── Critic              scores confidence per result
                    └── Contradiction Engine   cross-references claims across sources
                          └── Synthesizer      structured brief, inline [N] citations
```

**State machine:** LangGraph with full state persistence and checkpoint support
**Event streaming:** Redis Streams + Pub/Sub → SSE → frontend in real time
**LLMs:** Groq-hosted `llama-3.1-8b-instant` for planning/execution, `llama-3.3-70b-versatile` for synthesis only
**Vector memory:** Qdrant for semantic search across research findings
**Knowledge graph:** Neo4j for entity and relationship tracking
**Web search:** Tavily API

---

## Features

**Research**
- Depth selector — Quick (2 tasks, ~45s) / Standard (3 tasks, ~90s) / Deep (5 tasks, ~3min)
- Parallel task execution with concurrency control
- Inline `[N]` citations mapped to exact sources, ordered by synthesis sequence
- Contradiction detection — conflicting claims surfaced as cards with severity scoring
- Confidence scoring derived from source corroboration and contradiction count
- Refined query preview — see what was actually researched vs. what you typed

**Live view**
- Real-time progress arc with smooth percentage animation and in-stage creep
- Per-agent activity indicators (Planner / Executor / Critic / Synthesizer)
- Source chips appearing as found, task cards with status, estimated time remaining
- Agent event log with full action history

**Report**
- Section cards with numbered headings, table of contents, reading progress bar
- Clickable citation badges `[1]` `[2]` linked to source URLs with hover tooltips
- Contradiction cards — Claim A vs Claim B, severity dot-bar
- Confidence ring with animated fill
- Focus / reading mode (`⌘F`) — full-screen overlay, zero distraction
- Export as Markdown (`⌘E`), copy to clipboard

**Inline Q&A**
- Ask follow-up questions directly inside the report — no new search, no new tab
- Answers grounded in report context + broader LLM reasoning
- Q/A thread panel, not a chat bubble interface

**Home**
- Recent sessions with confidence badge, word count, source count, preview
- Depth selector, typing placeholder with examples, `⌘K` to focus

---

## Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph / LangChain |
| LLM Inference | Groq (llama-3.1-8b, llama-3.3-70b) |
| Vector Store | Qdrant |
| Knowledge Graph | Neo4j |
| Web Search | Tavily |
| Event Streaming | Redis Streams + Pub/Sub |
| Backend | FastAPI + Python 3.13 |
| Frontend | Next.js 15, Tailwind CSS, Framer Motion |
| Embeddings | SentenceTransformers (all-MiniLM-L6-v2) |

---

## Getting started

### Prerequisites

- Docker (for Redis, Qdrant, Neo4j)
- Python 3.11+
- Node.js 18+
- Groq API key (free tier works)
- Tavily API key (free tier works)

### 1. Clone

```bash
git clone https://github.com/1Ash0/Nexora.git
cd Nexora
```

### 2. Environment

```bash
cp .env.example .env
```

Fill in `.env`:

```env
GROQ_API_KEY=your_key
TAVILY_API_KEY=your_key
REDIS_URL=redis://localhost:6379/0
QDRANT_HOST=localhost
QDRANT_PORT=6333
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=research123
```

### 3. Start infrastructure

```bash
docker compose up -d
```

Starts Redis, Qdrant, Neo4j, and Postgres.

### 4. Backend

```bash
cd backend
pip install -r requirements.txt
cd ..
python run_backend.py
```

Runs on `http://localhost:8080`

### 5. Frontend

```bash
cd frontend
npm install
npm run dev
```

Runs on `http://localhost:3000`

---

## Project structure

```
Nexora/
├── backend/
│   ├── agents/
│   │   ├── planner.py           # Query decomposition, depth control
│   │   ├── executor.py          # Parallel task execution, web + vector search
│   │   ├── critic.py            # Confidence scoring per result
│   │   ├── contradiction_engine.py  # Cross-source conflict detection
│   │   └── synthesizer.py       # Report generation, citation mapping
│   ├── api/
│   │   ├── routes/
│   │   │   ├── research.py      # /start, /followup, /status endpoints
│   │   │   └── stream.py        # SSE event stream
│   │   ├── reporting.py         # Redis + in-memory event bus
│   │   └── main.py
│   ├── config/
│   │   └── prompts/             # synthesis.txt, executor.txt, planner.txt
│   ├── graph/
│   │   ├── workflow.py          # LangGraph state machine
│   │   └── state.py             # ResearchState TypedDict
│   ├── memory/
│   │   └── vector_store.py      # Qdrant async wrapper
│   └── utils/
│       └── rate_limiter.py      # Groq quota protection
├── frontend/
│   ├── app/
│   │   ├── page.tsx             # Home — search, depth, recent sessions
│   │   └── research/[sessionId]/page.tsx  # Live view + report
│   ├── components/
│   │   ├── SynthesisReport.tsx  # Report, citations, Q&A panel
│   │   └── NexoraShell.tsx      # Top nav shell
│   ├── store/
│   │   └── research.ts          # Zustand state + SSE event processing
│   └── hooks/
│       └── useSSE.ts            # EventSource with retry logic
├── docker-compose.yml
└── run_backend.py
```

---

## Design decisions

**Why small LMs for execution?**
Groq free tier is shared per org. `llama-3.1-8b-instant` has 5× the daily token budget of the 70b model. Planning and execution use the 8b model with direct JSON prompting (no tool-call schema validation failures). The 70b fires once, only at synthesis.

**Why Redis Streams over WebSockets?**
Streams persist events — if the client reconnects mid-research, it replays from the last consumed ID. WebSockets lose state on disconnect. The SSE generator uses `XREAD block=15000` and falls back to an in-memory bus if Redis is unavailable.

**Why LangGraph over a custom orchestrator?**
State persistence, checkpointing, and conditional edges out of the box. The contradiction check and critique are conditional nodes — they only run if the executor produces results worth checking.

**Why ordered sources in synthesis payload?**
The synthesizer numbers sources `[1]–[N]` at prompt time. The frontend's source store accumulates in arrival order, which may differ. Passing the ordered list in `synthesis_complete` ensures citation badges link to the exact right URL.

---

## Limitations

- Groq free tier: ~100k tokens/day on the 70b model. Deep research on complex queries can approach this limit.
- Tavily free tier: 1,000 searches/month. Each task uses 1–3 searches.
- No persistence across server restarts — Redis state is in-memory only unless you configure Redis persistence.
- SentenceTransformer model downloads ~90MB on first run.

---

## License

MIT
