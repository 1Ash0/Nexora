from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any

router = APIRouter()

@router.get("/graph/{session_id}")
async def get_graph_snapshot(session_id: str, request: Request):
    """
    Returns a D3-compatible snapshot of the knowledge graph for a specific session.
    """
    # Lifespan initialized clients are in app.state
    kg_client = request.app.state.kg_client
    
    try:
        snapshot = await kg_client.get_graph_snapshot(session_id)
        if not snapshot or not snapshot.get("nodes"):
            # Return empty structure instead of 404 to support empty starts
            return {"nodes": [], "links": []}
        return snapshot
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
