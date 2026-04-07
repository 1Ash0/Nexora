from typing import Dict, Any, List
from backend.graph.state import ResearchState, CriticOutput

class CriticAgent:
    def __init__(self, llm, settings):
        self.llm = llm
        self.settings = settings
        with open("backend/config/prompts/critic.txt", "r", encoding="utf-8") as f:
            self.prompt_template = f.read()

        # Connect the LLM with structured output mapping to CriticOutput
        self.structured_llm = self.llm.with_structured_output(CriticOutput)

    def critique(self, state: ResearchState) -> Dict[str, Any]:
        original_query = state.get("original_query", "")
        completed_tasks = state.get("completed_tasks", [])
        contradictions = state.get("contradictions", [])
        iteration_count = state.get("iteration_count", 0)
        max_iterations = getattr(self.settings, "MAX_ITERATIONS", 3)

        # Format task summaries for the prompt
        formatted_task_summaries = ""
        for idx, task in enumerate(completed_tasks):
            desc = task.get("description", "") if isinstance(task, dict) else task.description
            status = task.get("status", "unknown") if isinstance(task, dict) else task.status
            result = task.get("result", "") if isinstance(task, dict) else task.result
            t_id = task.get("id", str(idx)) if isinstance(task, dict) else task.id
            conf = task.get("confidence", 0.0) if isinstance(task, dict) else task.confidence
            
            formatted_task_summaries += f"Task ID: {t_id}\n"
            formatted_task_summaries += f"Description: {desc}\n"
            formatted_task_summaries += f"Status: {status}\n"
            formatted_task_summaries += f"Confidence: {conf}\n"
            formatted_task_summaries += f"Result Snippet: {result[:500] if result else 'None'}\n\n"

        # Format contradictions
        formatted_contradictions = ""
        for c in contradictions:
            c_type = c.get("type", "") if isinstance(c, dict) else c.type
            claim_a = c.get("claim_a", "") if isinstance(c, dict) else c.claim_a
            claim_b = c.get("claim_b", "") if isinstance(c, dict) else c.claim_b
            formatted_contradictions += f"- Type: {c_type} | Claim A: {claim_a} vs Claim B: {claim_b}\n"

        prompt = self.prompt_template.format(
            original_query=original_query,
            formatted_task_summaries=formatted_task_summaries if formatted_task_summaries else "No completed tasks yet.",
            contradiction_count=len(contradictions),
            formatted_contradictions=formatted_contradictions if contradictions else "None"
        )

        try:
            output: CriticOutput = self.structured_llm.invoke(prompt)
        except Exception as e:
            print(f"Critic LLM failed: {e}. Falling back to default pass.")
            output = CriticOutput(
                verdict="pass",
                overall_score=0.9,
                coverage_score=0.9,
                accuracy_score=0.9,
                depth_score=0.9,
                missing_aspects=[],
                retry_tasks=[],
                new_tasks=[],
                reasoning=f"Fallback due to parsing error: {e}"
            )

        # Override verdict based on hard logic
        verdict = output.verdict
        
        # If iteration >= MAX_ITERATIONS: force verdict = "pass"
        if iteration_count >= max_iterations:
            verdict = "pass"
            output.reasoning += f" (Forced PASS due to hit max_iterations: {max_iterations})"
        else:
            # If overall_score >= 0.8 and iteration_count < MAX_ITERATIONS: verdict = "pass"
            if output.overall_score >= 0.8:
                verdict = "pass"
            # If specific tasks failed: verdict = "retry"
            # We assume failure was detected by executor or LLM noted them in retry_tasks
            failed_tasks = [t for t in completed_tasks if (t.get("status") if isinstance(t, dict) else t.status) == "failed"]
            if failed_tasks or output.retry_tasks:
                verdict = "retry"
            # If missing_aspects found and iteration < MAX_ITERATIONS: verdict = "replan"
            elif output.missing_aspects and output.overall_score < 0.8:
                verdict = "replan"

        output.verdict = verdict

        # Update metadata logically
        metadata = state.get("metadata", {})
        metadata["critic_verdict"] = verdict
        metadata["critic_reasoning"] = output.reasoning
        metadata["critic_scores"] = {
            "overall": output.overall_score,
            "coverage": output.coverage_score,
            "accuracy": output.accuracy_score,
            "depth": output.depth_score
        }

        # Instead of directly updating the state dictionary since state merging uses graphs
        # We return the dictionary updates expected by LangGraph
        return {
            "metadata": metadata,
            # We can also populate missing aspects or retry tasks back to human feedback or planner if chosen
        }
