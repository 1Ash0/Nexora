import asyncio
from backend.memory.knowledge_graph import KnowledgeGraphClient
from backend.memory.vector_store import VectorMemory
from backend.config.settings import settings
import dotenv

dotenv.load_dotenv()

async def check():
    print("--- Neo4j Node Counts ---")
    kg = KnowledgeGraphClient(settings.NEO4J_URI, settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    try:
        async with kg.driver.session() as s:
            r = await s.run("MATCH (n) RETURN labels(n)[0] as type, count(n) as count ORDER BY count DESC")
            async for x in r:
                print(f"{x['type']}: {x['count']}")
            
            print("\n--- Edge Counts ---")
            r2 = await s.run("MATCH ()-[r]->() RETURN type(r) as type, count(r) as count")
            async for x in r2:
                print(f"{x['type']}: {x['count']}")
    except Exception as e:
        print(f"Neo4j Check Failed: {e}")
    finally:
        await kg.close()

    print("\n--- Qdrant Collection Status ---")
    vm = VectorMemory(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    try:
        collections = await vm.client.get_collections()
        for c in collections.collections:
            info = await vm.client.get_collection(c.name)
            print(f"Collection {c.name}: {info.points_count} points")
    except Exception as e:
        print(f"Qdrant Check Failed: {e}")
    finally:
        await vm.close()

if __name__ == "__main__":
    asyncio.run(check())
