import asyncio
from typing import Dict, Any

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from backend.config.settings import settings
from backend.graph.state import ResearchState, TaskItem
from backend.agents.planner import PlannerAgent
from backend.agents.executor import ExecutorAgent
from backend.agents.critic import CriticAgent
from backend.agents.contradiction_engine import ContradictionEngine
from backend.agents.synthesizer import SynthesizerAgent
from backend.tools import EXECUTOR_TOOLS
from backend.memory.vector_store import VectorMemory
from backend.memory.knowledge_graph import KnowledgeGraphClient
from backend.llm import create_chat_model


# ---------------------------------------------------------------------------
# 1. Component Factory
# ---------------------------------------------------------------------------
def get_agents() -> dict:
    llm = create_chat_model(temperature=0.0)
    syn_llm = create_chat_model(temperature=0.3)
    v_memory = VectorMemory(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    kg_client = KnowledgeGraphClient(uri=settings.NEO4J_URI, user=settings.NEO4J_USER, password=settings.NEO4J_PASSWORD)

    return {
        "planner": PlannerAgent(llm=llm, settings=settings, vector_memory=v_memory),
        "executor": ExecutorAgent(llm=llm, tools=EXECUTOR_TOOLS, vector_memory=v_memory, kg_client=kg_client, settings=settings),
        "critic": CriticAgent(llm=llm, settings=settings),
        "contradiction_engine": ContradictionEngine(llm=llm, settings=settings),
        "synthesizer": SynthesizerAgent(llm=syn_llm, settings=settings),
    }


# ---------------------------------------------------------------------------
# 2. Node functions
# ---------------------------------------------------------------------------
async def plan_node(state: ResearchState) -> Dict[str, Any]:
    return await get_agents()["planner"].plan(state)


async def execute_node(state: ResearchState) -> Dict[str, Any]:
    agents = get_agents()
    raw_tasks = state.get("task_graph", [])
    task_objs = [TaskItem.model_validate(t) if isinstance(t, dict) else t for t in raw_tasks]
    pending_tasks = [t for t in task_objs if t.status == "pending"]

    if not pending_tasks:
        return {"completed_tasks": [], "iteration_count": state["iteration_count"] + 1}

    limit = getattr(settings, "EXECUTOR_POOL_SIZE", 2)
    sem = asyncio.Semaphore(limit)

    async def _execute_with_sem(t: TaskItem):
        async with sem:
            return await agents["executor"].execute(t, state)

    results = await asyncio.gather(*[_execute_with_sem(t) for t in pending_tasks])

    all_completed, all_sources = [], []
    for r in results:
        all_completed.extend(r.get("completed_tasks", []))
        all_sources.extend(r.get("sources", []))

    return {
        "completed_tasks": all_completed,
        "sources": all_sources,
        "iteration_count": state["iteration_count"] + 1,
    }


async def contradiction_node(state: ResearchState) -> Dict[str, Any]:
    return await get_agents()["contradiction_engine"].detect(state)


def critique_node(state: ResearchState) -> Dict[str, Any]:
    return get_agents()["critic"].critique(state)


def synthesize_node(state: ResearchState) -> Dict[str, Any]:
    return get_agents()["synthesizer"].synthesize(state)


def human_review_node(state: ResearchState) -> Dict[str, Any]:
    return {}


# ---------------------------------------------------------------------------
# 3. Routing logic
# ---------------------------------------------------------------------------
def route_critique(state: ResearchState) -> str:
    if state.get("interrupt_requested"):
        return "human_review"

    verdict = (state.get("metadata") or {}).get("critic_verdict")

    if verdict == "pass":
        return "synthesize"
    if verdict == "replan" and state.get("iteration_count", 0) < settings.MAX_ITERATIONS:
        return "plan"
    if verdict == "retry" and state.get("iteration_count", 0) < settings.MAX_ITERATIONS:
        return "execute"

    return "synthesize"


# ---------------------------------------------------------------------------
# 4. Build StateGraph
# ---------------------------------------------------------------------------
graph = StateGraph(ResearchState)

graph.add_node("plan", plan_node)
graph.add_node("execute", execute_node)
graph.add_node("contradiction_check", contradiction_node)
graph.add_node("critique", critique_node)
graph.add_node("synthesize", synthesize_node)
graph.add_node("human_review", human_review_node)

graph.set_entry_point("plan")
graph.add_edge("plan", "execute")
graph.add_edge("execute", "contradiction_check")
graph.add_edge("contradiction_check", "critique")

graph.add_conditional_edges(
    "critique",
    route_critique,
    {
        "synthesize": "synthesize",
        "plan": "plan",
        "execute": "execute",
        "human_review": "human_review",
    },
)

graph.add_edge("human_review", "plan")
graph.add_edge("synthesize", END)


# ---------------------------------------------------------------------------
# 5. Compile Factory
# ---------------------------------------------------------------------------
def get_workflow(checkpointer=None):
    """
    Returns the compiled graph. Defaults to MemorySaver if no checkpointer provided.
    """
    cp = checkpointer or MemorySaver()
    return graph.compile(
        checkpointer=cp,
        interrupt_before=["human_review"],
    )
