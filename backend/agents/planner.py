import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any

from pydantic import BaseModel, Field

from backend.graph.state import ResearchState, TaskItem

class PlannerOutput(BaseModel):
    refined_query: str
    tasks: List[TaskItem] = Field(min_length=3, max_length=7)
    reasoning: str

    def validate_no_cycles(self):
        id_map = {t.id: t for t in self.tasks}
        visited = set()
        def dfs(node_id, path):
            if node_id in path: return True
            if node_id in visited: return False
            path.add(node_id)
            for dep in id_map.get(node_id, TaskItem(id=node_id, description="", status="pending", priority=1, dependencies=[])).dependencies:
                if dfs(dep, path): return True
            path.remove(node_id)
            visited.add(node_id)
            return False
        
        for t in self.tasks:
            if dfs(t.id, set()):
                raise ValueError("Cycle detected in task dependencies")

class PlannerAgent:
    def __init__(self, llm, settings, vector_memory):
        self.llm = llm
        self.settings = settings
        self.vector_memory = vector_memory
        with open("backend/config/prompts/planner.txt", "r", encoding="utf-8") as f:
            self.prompt_template = f.read()
            
    async def plan(self, state: ResearchState) -> Dict[str, Any]:
        query = state.get("original_query", "")
        feedback = state.get("human_feedback")
        iteration = state.get("iteration_count", 0)
        
        feedback_block = f"Human Feedback (incorporate this): {feedback}" if feedback else ""
        
        # 6a. Call vector_memory.semantic_search
        search_results = await self.vector_memory.semantic_search(query, top_k=5)
        
        # 6b. Add prior research context if found
        prior_context_block = ""
        missing_aspects_block = ""
        
        if search_results:
            context_texts = [res["text"] for res in search_results if "text" in res]
            if context_texts:
                prior_context_block = "Prior research context:\n" + "\n- ".join(context_texts)
        
        
        prompt = self.prompt_template.format(
            query=query,
            iteration=iteration,
            feedback_block=feedback_block,
            prior_context_block=prior_context_block,
            missing_aspects_block=missing_aspects_block
        )
        
        structured_llm = self.llm.with_structured_output(PlannerOutput)
        
        try:
            # First try
            output: PlannerOutput = structured_llm.invoke(prompt)
            output.validate_no_cycles()
        except Exception as e:
            # Retry once with error feedback
            retry_prompt = prompt + f"\n\nPrevious attempt failed: {str(e)}\nFix the error and output valid JSON without cycles."
            try:
                output: PlannerOutput = structured_llm.invoke(retry_prompt)
                output.validate_no_cycles()
            except Exception as retry_e:
                print(f"Planner LLM failed twice. Error: {retry_e}. Falling back.")
                fallback_tasks = [
                    TaskItem(id=str(uuid.uuid4()), description="Background context", status="pending", priority=1, dependencies=[]),
                    TaskItem(id=str(uuid.uuid4()), description="Current state of the art", status="pending", priority=1, dependencies=[]),
                    TaskItem(id=str(uuid.uuid4()), description="Comparative analysis", status="pending", priority=1, dependencies=[])
                ]
                output = PlannerOutput(
                    refined_query=f"{query} (refined)",
                    tasks=fallback_tasks,
                    reasoning=f"Fallback due to LLM error: {retry_e}"
                )
            
        # Converting elements to dict so they match standard TypedDict expectations and assertion tests subscripting
        tasks_as_dicts = [t.model_dump() for t in output.tasks]
            
        return {
            "refined_query": output.refined_query,
            "task_graph": tasks_as_dicts,
            "metadata": {
                "plan_reasoning": output.reasoning,
                "planned_at": datetime.now(timezone.utc).isoformat()
            }
        }
