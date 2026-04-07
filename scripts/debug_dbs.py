import asyncio
import hashlib
from neo4j import AsyncGraphDatabase
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from backend.config.settings import settings
from sentence_transformers import SentenceTransformer

async def debug_qdrant():
    print("Testing Qdrant...")
    client = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    coll_name = "test_debug"
    try:
        await client.delete_collection(coll_name)
    except:
        pass
    
    encoder = SentenceTransformer('all-MiniLM-L6-v2')
    vec = encoder.encode("Test chunk").tolist()
    print(f"Dimension generated: {len(vec)}")
    
    await client.create_collection(
        collection_name=coll_name,
        vectors_config=VectorParams(size=len(vec), distance=Distance.COSINE),
    )
    await client.create_payload_index(collection_name=coll_name, field_name="session_id", field_schema="keyword")
    
    import uuid
    point_id = str(uuid.uuid4())
    await client.upsert(
        collection_name=coll_name, 
        points=[PointStruct(id=point_id, vector=vec, payload={"session_id": "sess-1", "hash": "myhash", "text": "Test chunk"})],
        wait=True
    )
    
    res_scroll, _ = await client.scroll(
        collection_name=coll_name,
        scroll_filter=Filter(must=[FieldCondition(key="session_id", match=MatchValue(value="sess-1"))]),
        limit=10
    )
    print(f"Scroll found: {len(res_scroll)} points")
    
    res_search = await client.query_points(
        collection_name=coll_name,
        query=vec,
        query_filter=Filter(must=[FieldCondition(key="session_id", match=MatchValue(value="sess-1"))]),
        limit=10
        # No threshold first
    )
    print(f"Search found: {len(res_search.points)} points. Score: {res_search.points[0].score if res_search.points else 'N/A'}")
    
async def debug_neo4j():
    print("Testing Neo4j...")
    driver = AsyncGraphDatabase.driver(settings.NEO4J_URI, auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD))
    query = """
    MERGE (cl:Claim {id: 'claim_123'})
    ON CREATE SET cl.text = 'test text'
    SET cl.session_id = 'sess_123'
    WITH cl
    OPTIONAL MATCH (s:Source) WHERE s.id IN []
    WITH cl, collect(s) AS sources
    FOREACH (s IN sources | MERGE (cl)-[:SUPPORTED_BY]->(s))
    WITH cl
    
    // creating a dummy concept
    MERGE (c:Concept {id: 'conc_123'}) ON CREATE SET c.name = 'test concept'
    WITH cl
    OPTIONAL MATCH (c:Concept) WHERE c.id IN ['conc_123', 'fake_456']
    WITH cl, collect(c) AS concepts
    FOREACH (c IN concepts | MERGE (cl)-[:RELATES_TO]->(c))
    RETURN cl.id as id
    """
    async with driver.session() as session:
        result = await session.run(query)
        r = await result.single()
        print(f"Claim returned: {r}")
        
    query2 = """
    MATCH (n:Claim {id: 'claim_123'})
    OPTIONAL MATCH (n)-[r]->(m)
    RETURN n, r, m
    """
    async with driver.session() as session:
        result = await session.run(query2)
        async for rec in result:
            print(f"Snapshot edge found: n={rec['n']['id']} r={rec['r'].type if hasattr(rec['r'], 'type') and rec['r'] else rec['r']} m={rec['m']['id'] if rec['m'] else None}")
    await driver.close()

async def main():
    await debug_qdrant()
    await debug_neo4j()

if __name__ == "__main__":
    asyncio.run(main())
