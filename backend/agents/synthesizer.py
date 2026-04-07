import os
from typing import Dict, Any, List
import tiktoken
from datetime import datetime, timezone

from backend.graph.state import ResearchState, SynthesizerOutput

class SynthesizerAgent:
    def __init__(self, llm, settings):
        # Specific synthesizer requirements: temperature=0.3
        self.llm = llm
        self.settings = settings
        with open("backend/config/prompts/synthesis.txt", "r", encoding="utf-8") as f:
            self.prompt_template = f.read()
            
        self.structured_llm = self.llm.with_structured_output(SynthesizerOutput)
        self.encoding = tiktoken.get_encoding("cl100k_base") # Standard for gpt-4o

    def synthesize(self, state: ResearchState) -> Dict[str, Any]:
        original_query = state.get("original_query", "")
        refined_query = state.get("refined_query", "")
        completed_tasks = state.get("completed_tasks", [])
        contradictions = state.get("contradictions", [])
        sources = state.get("sources", [])
        human_feedback = state.get("human_feedback")
        
        # 1. Build Research Context with Token-Based Truncation (8,000 tokens as per guide)
        max_tokens = 8000
        research_parts = []
        for task in completed_tasks:
            desc = task.get("description", "") if isinstance(task, dict) else task.description
            result = task.get("result", "") if isinstance(task, dict) else task.result
            conf = task.get("confidence", 0.0) if isinstance(task, dict) else task.confidence
            
            part = f"### Task: {desc}\n"
            part += f"Confidence: {conf}\n"
            part += f"Findings: {result}\n\n"
            research_parts.append(part)
            
        research_context = "".join(research_parts)
        if len(self.encoding.encode(research_context)) > max_tokens:
            print(f"Warning: Synthesizer context exceeds {max_tokens} tokens. Truncating.")
            tokens = self.encoding.encode(research_context)[:max_tokens]
            research_context = self.encoding.decode(tokens) + "... [TRUNCATED]"
            
        # 2. Build Contradiction Context (Keep these full, usually small)
        contradictions_parts = []
        for idx, c in enumerate(contradictions):
            ctype = c.get("type", "unknown") if isinstance(c, dict) else c.type
            severity = c.get("severity", 0.0) if isinstance(c, dict) else c.severity
            cl_a = c.get("claim_a", "") if isinstance(c, dict) else c.claim_a
            cl_b = c.get("claim_b", "") if isinstance(c, dict) else c.claim_b
            
            parts = f"CONTRADICTION {idx+1}:\n"
            parts += f"Type: {ctype} (Severity: {severity})\n"
            parts += f"Conflict A: {cl_a}\n"
            parts += f"Conflict B: {cl_b}\n\n"
            contradictions_parts.append(parts)
            
        contradictions_context = "".join(contradictions_parts) if contradictions_parts else "No identified contradictions."
        
        human_feedback_context = f"Human Feedback (Incorporate during synthesis): {human_feedback}" if human_feedback else ""
        
        # 3. Final Prompt Assembly and Fail-safe Check
        prompt = self.prompt_template.format(
            original_query=original_query,
            refined_query=refined_query,
            research_context=research_context,
            contradictions_context=contradictions_context,
            human_feedback_context=human_feedback_context
        )
        
        # Pre-flight weight check
        prompt_tokens = self.encoding.encode(prompt)
        if len(prompt_tokens) > 11000:
            print(f"[synthesizer] Prompt exceeds safety limit ({len(prompt_tokens)} tokens). Pruning research context...")
            # If the whole prompt is too big, aggressively prune the research context further
            allowed_context_tokens = 11000 - (len(prompt_tokens) - len(self.encoding.encode(research_context)))
            research_context = self.encoding.decode(self.encoding.encode(research_context)[:allowed_context_tokens]) + "... [TRUNCATED FOR SPACE]"
            # Re-assemble
            prompt = self.prompt_template.format(
                original_query=original_query,
                refined_query=refined_query,
                research_context=research_context,
                contradictions_context=contradictions_context,
                human_feedback_context=human_feedback_context
            )

        try:
            output: SynthesizerOutput = self.structured_llm.invoke(prompt)
        except Exception as e:
            print(f"Synthesizer LLM failed: {e}. Falling back to basic report.")
            output = SynthesizerOutput(
                synthesis=f"# Research Report: {original_query}\n\n{research_context}\n\n## Contradictions\n{contradictions_context}",
                word_count=len(research_context.split()),
                source_count=len(sources),
                confidence_summary="Medium (Fallback generated due to LLM error)",
                key_findings=["Fallback research summary generated."]
            )
            
        return {
            "synthesis": output.synthesis,
            "metadata": {
                "synthesized_at": datetime.now(timezone.utc).isoformat(),
                "word_count": output.word_count,
                "source_count": output.source_count,
                "key_findings": output.key_findings,
                "confidence_summary": output.confidence_summary
            }
        }
