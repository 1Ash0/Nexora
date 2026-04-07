import asyncio
import os
from backend.memory.knowledge_graph import KnowledgeGraphClient
from backend.memory.vector_store import VectorMemory
from backend.config.settings import settings
import dotenv

dotenv.load_dotenv()

async def check():
    kg_client = KnowledgeGraphClient(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )
    v_memory = VectorMemory(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    
    # 1. Neo4j counts
    print("\n--- Neo4j Counts ---")
    async with kg_client.driver.session() as session:
        query = "MATCH (n:Claim) RETURN count(n) as count"
        res = await (await session.run(query)).single()
        print(f"Claim: {res['count']}")
        
        query = "MATCH (n:Concept) RETURN count(n) as count"
        res = await (await session.run(query)).single()
        print(f"Concept: {res['count']}")
        
        query = "MATCH (n:Source) RETURN count(n) as count"
        res = await (await session.run(query)).single()
        print(f"Source: {res['count']}")

        query = "MATCH ()-[r:RELATES_TO]->() RETURN count(r) as count"
        res = await (await session.run(query)).single()
        print(f"Edge RELATES_TO: {res['count']}")
        
        query = "MATCH ()-[r:SUPPORTED_BY]->() RETURN count(r) as count"
        res = await (await session.run(query)).single()
        print(f"Edge SUPPORTED_BY: {res['count']}")

    # 2. Qdrant check
    print("\n--- Qdrant Status ---")
    collection_info = await v_memory.client.get_collection("research_memory")
    print(f"Points in collection: {collection_info.points_count}")
    
    await kg_client.close()

if __name__ == "__main__":
    asyncio.run(check())
