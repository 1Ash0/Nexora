import asyncio
import hashlib
import uuid
import tiktoken
from datetime import datetime
from typing import List, Dict, Any

from pydantic import BaseModel, Field
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from backend.graph.state import ResearchState, TaskItem
from backend.llm import create_chat_model
from backend.memory.local_embeddings import LocalHashEmbeddings
from backend.memory.vector_store import VectorMemory
from backend.memory.knowledge_graph import KnowledgeGraphClient
from qdrant_client.models import PointStruct
import structlog

logger = structlog.get_logger(__name__)


class ClaimOutput(BaseModel):
    text: str
    source_url: str
    confidence: float = 0.5


class SourceOutput(BaseModel):
    url: str
    title: str
    snippet: str = ""


class ExecutorOutput(BaseModel):
    summary: str
    claims: List[ClaimOutput] = Field(default_factory=list)
    confidence: float = 0.5
    sources: List[SourceOutput] = Field(default_factory=list)


class ExecutorAgent:
    def __init__(self, llm, tools, vector_memory: VectorMemory, kg_client: KnowledgeGraphClient, settings):
        self.llm = llm
        self.tools = tools
        self.vector_memory = vector_memory
        self.kg_client = kg_client
        self.settings = settings

        with open("backend/config/prompts/executor.txt", "r", encoding="utf-8") as f:
            self.prompt_template = f.read()

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.prompt_template),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        agent = create_tool_calling_agent(llm, tools, prompt)
        self.agent_executor = AgentExecutor(
            agent=agent, tools=tools, max_iterations=6,
            handle_parsing_errors=True, verbose=True
        )

        self.parser_llm = create_chat_model(temperature=0.0).with_structured_output(ExecutorOutput)
        self.embeddings = LocalHashEmbeddings(dim=1536)
        self.encoder = tiktoken.get_encoding("cl100k_base")

    def _safe_truncate(self, text: str, max_tokens: int = 10000) -> str:
        """Truncate text to fit within a specified token budget."""
        tokens = self.encoder.encode(text)
        if len(tokens) <= max_tokens:
            return text
        print(f"[executor] Payload too large ({len(tokens)} tokens). Pruning to {max_tokens}...")
        return self.encoder.decode(tokens[:max_tokens]) + "... [TRUNCATED]"

    async def execute(self, task: TaskItem, state: ResearchState) -> Dict[str, Any]:
        original_query = state.get("original_query", "")
        session_id = state.get("session_id", "default_session")

        try:
            result = await self.agent_executor.ainvoke({
                "task_description": task.description,
                "original_query": original_query,
            })
            output_text = result.get("output", "")
            sanitized_text = output_text[:15_000]

            structured_result: ExecutorOutput | None = None
            for attempt in range(3):
                try:
                    # Pre-flight weight check before sending to parser
                    final_findings_text = self._safe_truncate(sanitized_text)
                    structured_result = await self.parser_llm.ainvoke(
                        "Parse the following research findings into the required structured format. "
                        "Summarize thoroughly.\n\nFindings:\n"
                        f"{final_findings_text}"
                    )
                    break
                except Exception as parse_err:
                    if "429" in str(parse_err):
                        wait = 10 * (attempt + 1)
                        print(f"[executor] Rate-limited; retrying parser in {wait}s...")
                        await asyncio.sleep(wait)
                    else:
                        raise

            if structured_result is None:
                raise ValueError("Parser failed after 3 retries (rate-limited).")

            chunks = [structured_result.summary] + [c.text for c in structured_result.claims]
            
            # 4a. Call vector_memory.upsert_chunks
            metadata = {
                "session_id": session_id,
                "task_id": task.id,
                "original_query": original_query,
            }
            await self.vector_memory.upsert_chunks(chunks, [metadata] * len(chunks))

            # 4c. Gather concept logic mock: (In reality we need to extract concepts from claims/summary. 
            # We will use dummy concept ids or just one overarching concept id)
            # Actually, per prompt, we just call upsert_concept for extracted concepts. 
            # I'll create a default concept based on the query, since we don't extract concepts yet explicitly.
            concept_id = await self.kg_client.upsert_concept(
                name=original_query.split()[:4][0] if original_query else "General",
                description=f"Concept related to {original_query}",
                session_id=session_id
            )
            
            # 4b. Prepare and Upsert Sources
            source_id_map = {}
            current_sources = list(structured_result.sources)
            
            # Create fallback sources if none are specified in structured output
            if not current_sources:
                current_sources = [
                    SourceOutput(
                        url=c.source_url,
                        title=f"Source for {c.text[:20]}...",
                        snippet=""
                    )
                    for c in structured_result.claims if c.source_url
                ]
            
            logger.info("upserting_sources", count=len(current_sources))
            for s in current_sources:
                sid = await self.kg_client.upsert_source(
                    url=s.url,
                    title=s.title,
                    session_id=session_id
                )
                source_id_map[s.url] = sid
                logger.info("source_upserted", sid=sid, url=s.url)

            # 4c. Call kg_client.add_claim
            logger.info("upserting_claims", count=len(structured_result.claims))
            for c in structured_result.claims:
                # Linking to specific relevant source IDs if possible
                current_source_ids = [source_id_map[c.source_url]] if c.source_url in source_id_map else list(source_id_map.values())
                
                await self.kg_client.add_claim(
                    text=c.text,
                    source_ids=current_source_ids,
                    concept_ids=[concept_id],
                    task_id=task.id,
                    session_id=session_id,
                    confidence=c.confidence
                )
                logger.info("claim_upserted", text=c.text[:50])

            task.status = "done"
            task.result = structured_result.summary[:500]
            task.confidence = structured_result.confidence
            task.claims = [c.model_dump() for c in structured_result.claims]

            sources = [s.model_dump() for s in current_sources]

            return {
                "completed_tasks": [task.model_dump()],
                "sources": sources,
                "graph_nodes": [],
                "graph_edges": [],
            }

        except Exception as e:
            print(f"[executor] Failed task {task.id}: {e}")
            task.status = "failed"
            task.result = f"Error: {str(e)[:200]}"
            return {
                "completed_tasks": [task.model_dump()],
                "sources": [],
                "graph_nodes": [],
                "graph_edges": [],
            }


