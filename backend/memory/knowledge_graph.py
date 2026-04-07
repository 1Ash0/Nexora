import asyncio
import hashlib
from typing import List, Dict, Any, Optional
from neo4j import AsyncGraphDatabase, exceptions
import structlog

logger = structlog.get_logger()

class KnowledgeGraphClient:
    def __init__(self, uri, user, password):
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
        self._initialized = False

    async def initialize(self):
        """Lazy initialization for schema setup."""
        if not self._initialized:
            await self.setup_schema()
            self._initialized = True

    async def setup_schema(self):
        """Run constraints and indexes for the research graph."""
        queries = [
            "CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT claim_id IF NOT EXISTS FOR (c:Claim) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT source_id IF NOT EXISTS FOR (s:Source) REQUIRE s.id IS UNIQUE",
            "CREATE INDEX concept_name IF NOT EXISTS FOR (c:Concept) ON (c.name)"
        ]
        
        async with self.driver.session() as session:
            for query in queries:
                try:
                    await session.run(query)
                except exceptions.ClientError as e:
                    logger.warning("schema_setup_warning", query=query, error=str(e))

    async def upsert_source(self, url: str, title: str, session_id: str) -> str:
        """MERGE source by URL."""
        source_id = hashlib.sha256(url.strip().encode()).hexdigest()
        query = """
        MERGE (s:Source {id: $id})
        ON CREATE SET s.url = $url, s.title = $title, s.session_id = $session_id, s.created_at = datetime()
        ON MATCH SET s.title = $title, s.updated_at = datetime()
        RETURN s.id as id
        """
        async with self.driver.session() as session:
            result = await session.run(query, id=source_id, url=url, title=title, session_id=session_id)
            record = await result.single()
            return record["id"]

    async def upsert_concept(self, name: str, description: str, session_id: str) -> str:
        """MERGE concept by normalized name."""
        concept_id = hashlib.sha256(name.lower().strip().encode()).hexdigest()
        query = """
        MERGE (c:Concept {id: $id})
        ON CREATE SET c.name = $name, c.description = $description, c.session_id = $session_id, c.created_at = datetime()
        ON MATCH SET c.description = $description
        RETURN c.id as id
        """
        async with self.driver.session() as session:
            result = await session.run(query, id=concept_id, name=name, description=description, session_id=session_id)
            record = await result.single()
            return record["id"]

    async def add_claim(self, text: str, source_ids: List[str], concept_ids: List[str], 
                        task_id: str, session_id: str, confidence: float) -> str:
        """CREATE claim node and connect to sources/concepts with relation counts."""
        claim_id = hashlib.sha256(f"{text}-{session_id}".encode()).hexdigest()
        
        # Explicit MATCH safety: We use a subquery/WITH logic instead of UNWIND.
        # This prevents row-collapse natively while still returning creation metrics.
        query = """
        MERGE (cl:Claim {id: $id})
        ON CREATE SET 
            cl.text = $text, 
            cl.task_id = $task_id, 
            cl.confidence = $confidence,
            cl.created_at = datetime()
        SET cl.session_id = $session_id, cl.updated_at = datetime()
        WITH cl
        
        // Link Sources
        OPTIONAL MATCH (s:Source) WHERE s.id IN $source_ids
        WITH cl, collect(s) AS sources
        FOREACH (s IN sources | MERGE (cl)-[:SUPPORTED_BY]->(s))
        WITH cl, size(sources) AS source_count
        
        // Link Concepts
        OPTIONAL MATCH (c:Concept) WHERE c.id IN $concept_ids
        WITH cl, source_count, collect(c) AS concepts
        FOREACH (c IN concepts | MERGE (cl)-[:RELATES_TO]->(c))
        
        RETURN cl.id as id, source_count, size(concepts) AS concept_count
        """
        
        async with self.driver.session() as session:
            result = await session.run(query, id=claim_id, text=text, source_ids=source_ids, 
                                       concept_ids=concept_ids, task_id=task_id, 
                                       session_id=session_id, confidence=confidence)
            record = await result.single()
            if not record:
                raise ValueError(f"Failed to upsert claim {claim_id}. Transaction returned no data.")
                
            logger.info("claim_linked", 
                       claim_id=record["id"], 
                       linked_sources=record["source_count"], 
                       linked_concepts=record["concept_count"])
                       
            return record["id"]

    async def add_contradiction(self, claim_a_id: str, claim_b_id: str, 
                                type: str, severity: float, explanation: str) -> str:
        con_id = hashlib.sha256(f"{claim_a_id}-{claim_b_id}".encode()).hexdigest()
        query = """
        MATCH (a:Claim {id: $a_id}), (b:Claim {id: $b_id})
        CREATE (cn:Contradiction {
            id: $id,
            type: $type,
            severity: $severity,
            explanation: $explanation,
            created_at: datetime()
        })
        CREATE (cn)-[:INVOLVES]->(a)
        CREATE (cn)-[:INVOLVES]->(b)
        CREATE (a)-[:CONTRADICTS {severity: $severity}]->(b)
        CREATE (b)-[:CONTRADICTS {severity: $severity}]->(a)
        RETURN cn.id as id
        """
        async with self.driver.session() as session:
            result = await session.run(query, id=con_id, a_id=claim_a_id, b_id=claim_b_id, 
                                       type=type, severity=severity, explanation=explanation)
            record = await result.single()
            return record["id"]

    async def get_graph_snapshot(self, session_id: str) -> Dict[str, Any]:
        """Return D3-compatible serializable graph representation."""
        query = """
        MATCH (n) WHERE n.session_id = $session_id OR n:Contradiction
        OPTIONAL MATCH (n)-[r]->(m)
        RETURN n, r, m
        """
        nodes = {}
        links = []
        
        async with self.driver.session() as session:
            result = await session.run(query, session_id=session_id)
            async for record in result:
                # DEBUG PRINT:
                print(f"SNAPSHOT RECORD: n={record['n']} r={record['r']} m={record['m']}")
                node_n = record["n"]
                if node_n and node_n["id"] not in nodes:
                    nodes[node_n["id"]] = {
                        "id": node_n["id"],
                        "label": node_n.get("name") or (node_n.get("text", "")[:30] + "..." if node_n.get("text") else ""),
                        "type": list(node_n.labels)[0] if node_n.labels else "Unknown",
                        "confidence": node_n.get("confidence", 1.0),
                        "properties": dict(node_n)
                    }
                
                node_m = record["m"]
                rel = record["r"]
                if node_m is not None and rel is not None:
                    if node_m["id"] not in nodes:
                        nodes[node_m["id"]] = {
                            "id": node_m["id"],
                            "label": node_m.get("name") or (node_m.get("text", "")[:30] + "..." if node_m.get("text") else ""),
                            "type": list(node_m.labels)[0] if node_m.labels else "Unknown",
                            "confidence": node_m.get("confidence", 1.0),
                            "properties": dict(node_m)
                        }
                    links.append({
                        "source": node_n["id"],
                        "target": node_m["id"],
                        "type": rel.type,
                        "properties": dict(rel)
                    })
        print(f"DEBUG RETURNING links: {links}")
        return {"nodes": list(nodes.values()), "edges": links}


    async def close(self):
        await self.driver.close()
