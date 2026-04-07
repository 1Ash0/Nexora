import asyncio
import math
import uuid
from typing import List, Literal
from pydantic import BaseModel, Field

from backend.graph.state import ResearchState, Contradiction
from backend.memory.local_embeddings import LocalHashEmbeddings


class ContradictionLLMOutput(BaseModel):
    contradicts: bool
    type: Literal["direct", "methodological", "scope"] = "direct"
    severity: float = Field(default=0.5, ge=0.0, le=1.0)
    explanation: str = ""


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 1e-12 or nb <= 1e-12:
        return 0.0
    return dot / (na * nb)


class ContradictionEngine:
    def __init__(self, llm, settings):
        self.llm = llm
        self.settings = settings
        with open("backend/config/prompts/contradiction.txt", "r", encoding="utf-8") as f:
            self.prompt_template = f.read()

        self.structured_llm = self.llm.with_structured_output(ContradictionLLMOutput)
        self.embeddings = LocalHashEmbeddings(dim=1536)

    async def detect(self, state: ResearchState) -> dict:
        completed_tasks = state.get("completed_tasks") or []

        all_claims = []
        for task in completed_tasks:
            raw_claims = task.get("claims") if isinstance(task, dict) else getattr(task, "claims", None)
            for c in (raw_claims or []):
                if isinstance(c, dict) and "text" in c:
                    all_claims.append(c)
                elif hasattr(c, "text"):
                    all_claims.append({"text": c.text, "source_url": getattr(c, "source_url", "")})

        if len(all_claims) < 2:
            return {"contradictions": [], "graph_edges": []}

        claim_texts = [c["text"][:2000] for c in all_claims]
        try:
            embs = self.embeddings.embed_documents(claim_texts)
        except Exception as e:
            print(f"[contradiction] Embedding failed: {e}")
            return {"contradictions": [], "graph_edges": []}

        threshold = 0.75
        max_pairs = 30
        pairs = []

        for i in range(len(all_claims)):
            for j in range(i + 1, len(all_claims)):
                sim = _cosine(embs[i], embs[j])
                if sim > threshold:
                    src_a = all_claims[i].get("source_url", "a")
                    src_b = all_claims[j].get("source_url", "b")
                    if src_a != src_b:
                        pairs.append((i, j, sim))

        pairs.sort(key=lambda x: -x[2])
        top_pairs = pairs[:max_pairs]
        if not top_pairs:
            return {"contradictions": [], "graph_edges": []}

        new_contradictions = []
        graph_edges = []

        for i, j, _ in top_pairs:
            claim_a = all_claims[i]
            claim_b = all_claims[j]
            try:
                out = await self._classify_pair(
                    claim_a.get("text", ""),
                    claim_b.get("text", ""),
                    claim_a.get("source_url", "Unknown A"),
                    claim_b.get("source_url", "Unknown B"),
                )

                if out.get("contradicts"):
                    cid = str(uuid.uuid4())
                    c_model = Contradiction(
                        id=cid,
                        source_a=claim_a.get("source_url", "Unknown A"),
                        source_b=claim_b.get("source_url", "Unknown B"),
                        claim_a=claim_a.get("text", ""),
                        claim_b=claim_b.get("text", ""),
                        type=out.get("type", "direct"),
                        severity=out.get("severity", 0.5),
                        resolution=None,
                    )
                    new_contradictions.append(c_model.model_dump())
                    graph_edges.append({
                        "source": f"claim_{i}",
                        "target": f"claim_{j}",
                        "type": "CONTRADICTS",
                        "properties": {
                            "severity": out.get("severity", 0.5),
                            "explanation": out.get("explanation", ""),
                        },
                    })
            except Exception as e:
                print(f"[contradiction] Classification failed for pair {i}-{j}: {e}")

        return {"contradictions": new_contradictions, "graph_edges": graph_edges}

    async def _classify_pair(self, claim_a: str, claim_b: str, source_a: str, source_b: str) -> dict:
        prompt = self.prompt_template.format(
            claim_a=claim_a[:1000],
            source_a=source_a,
            claim_b=claim_b[:1000],
            source_b=source_b,
        )
        res: ContradictionLLMOutput = await asyncio.to_thread(self.structured_llm.invoke, prompt)
        return res.model_dump()
