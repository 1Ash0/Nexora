import sys
import pytest
import asyncio
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from httpx import AsyncClient, ASGITransport
from backend.api.main import app

@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="module")
async def client():
    # Use ASGITransport to trigger the FastAPI app directly
    # To run lifespan, we can enter the LifespanContext if needed manually
    # but the simplest way is to manually initialize the app state for tests if it's missing
    
    # Triggering lifespan manually if not already (FastAPI's TestClient does this, but AsyncClient might not unless using Starlette's TestClient)
    # Actually, ASGITransport DOES NOT trigger lifespan by default.
    # We must use lifepsan = True or a context manager.
    
    from contextlib import asynccontextmanager
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Manually trigger startup since ASGITransport doesn't
        from backend.api.main import lifespan
        async with lifespan(app):
            yield ac

@pytest.mark.anyio
async def test_research_lifecycle(client):
    # Start research
    response = await client.post("/api/v1/research", json={
        "query": "What are the latest developments in protein folding AI?"
    })
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    session_id = data["session_id"]
    
    # Poll status
    await asyncio.sleep(5)
    status_resp = await client.get(f"/api/v1/research/{session_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["session_id"] == session_id
    
    # Test graph endpoint
    graph_resp = await client.get(f"/api/v1/graph/{session_id}")
    assert graph_resp.status_code == 200
    graph_data = graph_resp.json()
    assert "nodes" in graph_data
    # edges might be missing if it hasn't processed much, but keys should exist
    assert "edges" in graph_data or "links" in graph_data

@pytest.mark.anyio
async def test_unknown_session(client):
    resp = await client.get("/api/v1/research/nonexistent-session")
    assert resp.status_code == 404

@pytest.mark.anyio
async def test_interrupt_not_started(client):
    resp = await client.post("/api/v1/interrupt/fake-session", json={"reason": "test reason"})
    assert resp.status_code == 404
