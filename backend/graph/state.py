from __future__ import annotations

import operator
from typing import Annotated, List, Literal, Optional, TypedDict
from pydantic import BaseModel, Field

class TaskItem(BaseModel):
    id: str
    description: str
    status: Literal["pending", "running", "done", "failed"] = "pending"
    priority: int = Field(default=1, ge=1, le=5)
    dependencies: List[str] = Field(default_factory=list)
    result: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0, le=1)
    agent_id: Optional[str] = None
    claims: Optional[List[dict]] = Field(default_factory=list)

class Contradiction(BaseModel):
    id: str
    source_a: str
    source_b: str
    claim_a: str
    claim_b: str
    type: Literal["direct", "methodological", "scope"]
    severity: float = Field(ge=0, le=1)
    resolution: Optional[str] = None

class CriticOutput(BaseModel):
    verdict: Literal["pass", "replan", "retry"]
    overall_score: float
    coverage_score: float
    accuracy_score: float
    depth_score: float
    missing_aspects: List[str]
    retry_tasks: List[str]
    new_tasks: List[TaskItem]
    reasoning: str

class SynthesizerOutput(BaseModel):
    synthesis: str
    word_count: int
    source_count: int
    confidence_summary: str
    key_findings: List[str]

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

def get_initial_state(query: str, session_id: str) -> ResearchState:
    return {
        "session_id": session_id,
        "original_query": query,
        "refined_query": "",
        "task_graph": [],
        "completed_tasks": [],
        "contradictions": [],
        "sources": [],
        "synthesis": "",
        "iteration_count": 0,
        "interrupt_requested": False,
        "human_feedback": None,
        "graph_nodes": [],
        "graph_edges": [],
        "error": None,
        "metadata": {}
    }
