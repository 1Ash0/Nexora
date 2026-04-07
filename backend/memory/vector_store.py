import uuid
import hashlib
import numpy as np
from typing import List, Dict, Any, Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer
import asyncio

class VectorMemory:
    def __init__(self, host="127.0.0.1", port=6333, collection_name="research_memory"):
        self.client = AsyncQdrantClient(host=host, port=port)
        self.collection_name = collection_name
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2') 
        self.vector_dim = 384 

    async def ensure_collection(self):
        collections = await self.client.get_collections()
        exists = any(c.name == self.collection_name for c in collections.collections)
        
        if not exists:
            await self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_dim, distance=Distance.COSINE),
            )
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="session_id",
                field_schema="keyword",
            )
            await self.client.create_payload_index(
                collection_name=self.collection_name,
                field_name="hash",
                field_schema="keyword",
            )

    def _get_embedding(self, text: str) -> List[float]:
        return self.encoder.encode(text).tolist()

    async def upsert_chunks(self, chunks: List[str], metadata_list: List[Dict[str, Any]]):
        await self.ensure_collection()
        
        points = []
        for text, meta in zip(chunks, metadata_list):
            content_hash = hashlib.sha256(text.encode()).hexdigest()
            
            records, _ = await self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(must=[FieldCondition(key="hash", match=MatchValue(value=content_hash))]),
                limit=1
            )
            
            if not records:
                vector = self._get_embedding(text)
                point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, content_hash))
                combined_payload = {**meta, "hash": content_hash, "text": text}
                points.append(PointStruct(id=point_id, vector=vector, payload=combined_payload))
        
        if points:
            for i in range(0, len(points), 100):
                batch = points[i:i+100]
                # wait=True forces Qdrant to flush to disk before returning, ensuring 
                # subsequent searches in the same session immediately find the new points.
                await self.client.upsert(collection_name=self.collection_name, points=batch, wait=True)

    async def semantic_search(self, query: str, session_id: Optional[str] = None, 
                              top_k: int = 10) -> List[Dict[str, Any]]:
        """Standard semantic search with explicitly defined structure mapping."""
        query_vector = self._get_embedding(query)
        
        search_filter = None
        if session_id:
            search_filter = Filter(must=[FieldCondition(key="session_id", match=MatchValue(value=session_id))])
            
        # Using the v1.17 query_points API without explicit threshold to rule out cosine distance drop
        results = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=search_filter,
            limit=top_k
        )
        
        # ScoredPoint safe accessor
        return [
            {"text": r.payload.get("text", ""), "score": r.score, "metadata": r.payload} 
            for r in results.points if hasattr(r, "payload") and r.payload is not None
        ]

    async def mmr_search(self, query: str, session_id: str, top_k: int = 10, 
                        lambda_mult: float = 0.5) -> List[Dict[str, Any]]:
        query_vector = np.array(self._get_embedding(query))
        
        search_filter = Filter(must=[FieldCondition(key="session_id", match=MatchValue(value=session_id))])
        candidates_result = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector.tolist(),
            query_filter=search_filter,
            limit=30,
            with_vectors=True
        )
        candidates = candidates_result.points
        
        if not candidates:
            return []

        selected_indices = []
        while len(selected_indices) < min(top_k, len(candidates)):
            mmr_scores = []
            for i, p in enumerate(candidates):
                if i in selected_indices:
                    mmr_scores.append(-1.0)
                    continue
                
                cand_vec = np.array(p.vector)
                relevance = np.dot(cand_vec, query_vector) / (np.linalg.norm(cand_vec) * np.linalg.norm(query_vector))
                
                redundancy = 0
                if selected_indices:
                    redundancy = max([
                        np.dot(cand_vec, np.array(candidates[j].vector)) / (np.linalg.norm(cand_vec) * np.linalg.norm(np.array(candidates[j].vector)))
                        for j in selected_indices
                    ])
                
                score = lambda_mult * relevance - (1 - lambda_mult) * redundancy
                mmr_scores.append(score)
                
            selected_indices.append(np.argmax(mmr_scores))

        return [
            {"text": candidates[i].payload.get("text", ""), "score": candidates[i].score, "metadata": candidates[i].payload} 
            for i in selected_indices if hasattr(candidates[i], "payload") and candidates[i].payload is not None
        ]

    async def get_session_summary(self, session_id: str) -> str:
        records, _ = await self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(must=[FieldCondition(key="session_id", match=MatchValue(value=session_id))]),
            limit=50
        )
        full_text = " ".join([r.payload.get("text", "") for r in records if r.payload])
        return full_text[:12000] 

    async def close(self):
        pass
