from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime

class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=10, max_length=500)
    session_id: Optional[str] = None

class ResearchResponse(BaseModel):
    session_id: str
    status: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ResumeRequest(BaseModel):
    feedback: str
    action: Literal["continue", "replan", "abort"]

class TaskItemResponse(BaseModel):
    id: str
    description: str
    status: str
    priority: int
    dependencies: List[str]
    result: Optional[str] = None

class ResearchStateResponse(BaseModel):
    original_query: str
    session_id: str
    iteration_count: int
    task_graph: List[TaskItemResponse]
    human_feedback: Optional[str] = None
    interrupt_requested: bool = False
