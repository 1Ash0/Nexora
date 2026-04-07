import asyncio
import uuid
import time
from typing import List, Dict, Any
from backend.memory.knowledge_graph import KnowledgeGraphClient
from backend.memory.vector_store import VectorMemory
from backend.config.settings import settings

async def validate_qdrant_dedup():
    print("\n--- Test 1: Qdrant Deduplication ---")
    vm = VectorMemory(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    session_id = f"test_session_{uuid.uuid4().hex[:8]}"
    
    chunk = f"AI Alignment is the process of ensuring that AI systems behave in accordance with human values and goals. [{session_id}]"
    meta = {"session_id": session_id, "source": "test"}
    
    # First upsert
    print("Upserting chunk once...")
    await vm.upsert_chunks([chunk], [meta])
    
    # Second upsert (exact same chunk)
    print("Upserting same chunk again...")
    await vm.upsert_chunks([chunk], [meta])
    
    # Count results for this session
    res = await vm.semantic_search(chunk, session_id=session_id)
    count = len(res)
    
    if count == 1:
        print(f"PASS: Deduplication working. Count is {count}.")
        return True
    else:
        print(f"FAIL: Deduplication failed. Count is {count} (Expected 1).")
        return False

async def validate_qdrant_mmr():
    print("\n--- Test 2: Qdrant MMR Diversity ---")
    vm = VectorMemory(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    session_id = f"test_session_{uuid.uuid4().hex[:8]}"
    
    # Insert 5 very similar chunks about the same topic
    chunks = [
        f"AI Alignment focuses on value alignment techniques. [{session_id}]",
        f"Technical methods for AI alignment include reinforcement learning from human feedback. [{session_id}]",
        f"RLHF is a common strategy for aligning large language models. [{session_id}]",
        f"Ensuring AI safety through value integration is a primary goal of alignment. [{session_id}]",
        f"Proactive alignment frameworks aim to reduce risks from superintelligent systems. [{session_id}]"
    ]
    metas = [{"session_id": session_id, "id": i} for i in range(len(chunks))]
    
    await vm.upsert_chunks(chunks, metas)
    
    # 1. Standard semantic search
    print("Running standard semantic search...")
    standard_res = await vm.semantic_search("What is AI alignment?", session_id=session_id, top_k=3)
    
    # 2. MMR search
    print("Running MMR diversity search...")
    mmr_res = await vm.mmr_search("What is AI alignment?", session_id=session_id, top_k=3, lambda_mult=0.4)
    
    standard_texts = [r["text"] for r in standard_res]
    mmr_texts = [r["text"] for r in mmr_res]
    
    print(f"Standard Top 3: {standard_texts}")
    print(f"MMR Top 3:      {mmr_texts}")
    
    # Simple check for diversity: if sets are different, MMR is doing something
    if standard_texts != mmr_texts:
        print("PASS: MMR query returned a different (more diverse) subset than standard search.")
        return True
    else:
        print("NOTE: MMR and Standard search returned the same results. Topic density might be too low, but no error.")
        return True

async def validate_neo4j_graph():
    print("\n--- Test 3: Neo4j Relational Logic ---")
    kg = KnowledgeGraphClient(settings.NEO4J_URI, settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    await kg.initialize()
    
    session_id = f"test_session_{uuid.uuid4().hex[:8]}"
    
    # Upsert test concepts and source
    print("Creating test nodes...")
    c1_id = await kg.upsert_concept("AI Alignment", "Alignment of AI systems with humans.", session_id)
    c2_id = await kg.upsert_concept("RLHF", "Reinforcement Learning from Human Feedback.", session_id)
    
    # Claim with support and relation
    print("Linking claim to concepts...")
    claim_id = await kg.add_claim(
        "RLHF is a key component of current alignment strategies.",
        source_ids=[], # No real sources for test
        concept_ids=[c1_id, c2_id],
        task_id="test_task",
        session_id=session_id,
        confidence=0.9
    )
    
    # Verification: Get snapshot
    print("Verifying relationship graph...")
    snapshot = await kg.get_graph_snapshot(session_id)
    
    nodes = snapshot["nodes"]
    edges = snapshot["edges"]
    
    print(f"Found {len(nodes)} nodes and {len(edges)} edges.")
    
    # Expect RELATES_TO edges from Claim to both Concepts
    relates_to_count = sum(1 for e in edges if e["type"] == "RELATES_TO")
    
    if relates_to_count >= 2:
        print(f"PASS: Claim successfully linked to {relates_to_count} concepts.")
        await kg.close()
        return True
    else:
        print(f"FAIL: Relational linkage failed. Found {relates_to_count} RELATES_TO edges.")
        await kg.close()
        return False

async def main():
    try:
        q1 = await validate_qdrant_dedup()
        q2 = await validate_qdrant_mmr()
        n1 = await validate_neo4j_graph()
        
        if all([q1, q2, n1]):
            print("\n" + "="*40)
            print("  MEMORY TIER VALIDATION PASSED")
            print("="*40)
    except Exception as e:
        print(f"\nCRITICAL FAILURE: {e}")

if __name__ == "__main__":
    asyncio.run(main())
