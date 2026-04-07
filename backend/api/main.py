import sys
import asyncio
import structlog
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import settings
from backend.api.routes import research, stream, control, graph
from backend.memory.knowledge_graph import KnowledgeGraphClient
from backend.memory.vector_store import VectorMemory
from backend.graph.workflow import get_workflow
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
import redis.asyncio as redis

# Setup structured logging
structlog.configure(
    processors=[
        structlog.processors.JSONRenderer()
    ]
)
logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize clients
    logger.info("startup", message="Initializing memory and graph clients")
    
    # These clients are usually long-lived drivers
    app.state.kg_client = KnowledgeGraphClient(
        uri=settings.NEO4J_URI,
        user=settings.NEO4J_USER,
        password=settings.NEO4J_PASSWORD
    )
    app.state.vector_memory = VectorMemory(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT
    )
    # PostgreSQL Connection Pool for Checkpointing
    app.state.db_pool = AsyncConnectionPool(
        conninfo=settings.DATABASE_URL,
        max_size=20,
        kwargs={"autocommit": True}
    )
    await app.state.db_pool.open()
    
    app.state.checkpointer = AsyncPostgresSaver(app.state.db_pool)
    await app.state.checkpointer.setup()
    
    # Compile graph with persistence
    app.state.graph = get_workflow(checkpointer=app.state.checkpointer)
    
    # Redis Client
    app.state.redis = redis.from_url(settings.REDIS_URL, decode_responses=True)
    
    # Initialize Neo4j schema
    await app.state.kg_client.initialize()
    
    yield
    
    # Shutdown: Close connections
    logger.info("shutdown", message="Closing client connections")
    await app.state.kg_client.driver.close()
    await app.state.redis.close()
    await app.state.db_pool.close()

app = FastAPI(title="Nexora Research API", lifespan=lifespan)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Routers
app.include_router(research.router, prefix="/api/v1", tags=["research"])
app.include_router(stream.router, prefix="/api/v1", tags=["stream"])
app.include_router(control.router, prefix="/api/v1", tags=["control"])
app.include_router(graph.router, prefix="/api/v1", tags=["graph"])

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "services": {
            "neo4j": "connected",
            "qdrant": "connected",
            "redis": "connected"
        }
    }
