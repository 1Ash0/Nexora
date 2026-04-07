import asyncio
import uuid
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from backend.api.schemas import ResearchRequest, ResearchResponse, ResearchStateResponse
from backend.graph.workflow import get_workflow
from backend.graph.state import ResearchState

router = APIRouter()

@router.post("/research", response_model=ResearchResponse)
async def initiate_research(request: ResearchRequest, req: Request):
    session_id = request.session_id or str(uuid.uuid4())
    workflow = req.app.state.graph
    
    # Check if session exists (though our checkpointer handles upserts)
    # For now, we allow overwrite or resume by default, but a real 409 check 
    # would involve querying the checkpointer for existence.
    
    initial_state = ResearchState(
        original_query=request.query,
        session_id=session_id,
        iteration_count=0,
        task_graph=[],
        human_feedback=None,
        interrupt_requested=False
    )
    
    # Run graph in background
    config = {"configurable": {"thread_id": session_id}}
    
    # We use asyncio.create_task to run the graph so we can return early
    asyncio.create_task(workflow.ainvoke(initial_state, config=config))
    
    return ResearchResponse(session_id=session_id, status="started")

@router.get("/research/{session_id}", response_model=ResearchStateResponse)
async def get_research_status(session_id: str, req: Request):
    workflow = req.app.state.graph
    config = {"configurable": {"thread_id": session_id}}
    state = await workflow.aget_state(config)
    
    # Check if the state is actually populated
    if not state or not state.values or "original_query" not in state.values:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
    return ResearchStateResponse(**state.values)
