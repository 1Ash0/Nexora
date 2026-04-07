import asyncio
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from backend.api.routes.stream import _publish_event

router = APIRouter()

class InterruptRequest(BaseModel):
    reason: str

class ResumeRequest(BaseModel):
    feedback: str
    action: Literal["continue", "replan", "abort"]

@router.post("/interrupt/{session_id}")
async def interrupt_session(session_id: str, request: InterruptRequest, req: Request):
    graph = req.app.state.graph
    config = {"configurable": {"thread_id": session_id}}
    
    # 1. Load current checkpoint
    state = await graph.aget_state(config)
    if not state or not state.values:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # 2. Check if already interrupted
    if state.values.get("interrupt_requested"):
        raise HTTPException(status_code=409, detail="Already interrupted")
        
    # 3. Update state: interrupt_requested=True, metadata.interrupt_reason=reason
    await graph.aupdate_state(config, {
        "interrupt_requested": True,
        "metadata": {
            **(state.values.get("metadata", {})),
            "interrupt_reason": request.reason
        }
    })
    
    # 4. Save updated checkpoint (aupdate_state handles this)
    
    # 5. Publish SSE event
    await _publish_event(session_id, {
        "type": "interrupt_requested",
        "reason": request.reason
    })
    
    return {"status": "interrupted", "session_id": session_id}

@router.post("/resume/{session_id}")
async def resume_session(session_id: str, request: ResumeRequest, req: Request):
    graph = req.app.state.graph
    config = {"configurable": {"thread_id": session_id}}
    
    # 1. Load checkpoint
    state = await graph.aget_state(config)
    if not state or not state.values:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # 2. Check if interrupted
    if not state.values.get("interrupt_requested"):
        raise HTTPException(status_code=409, detail="Session is not in interrupted state")
        
    # 3. If action == "abort": publish synthesis_complete with partial results
    if request.action == "abort":
        await _publish_event(session_id, {
            "type": "synthesis_complete",
            "message": "Research aborted by user",
            "partial_results": True
        })
        return {"status": "aborted", "session_id": session_id}
        
    # 4. Update state: interrupt_requested=False, human_feedback=feedback, [replan logic]
    # If action=="replan": set task_graph back to [] (force replan)
    update = {
        "interrupt_requested": False,
        "human_feedback": request.feedback
    }
    if request.action == "replan":
        update["task_graph"] = []
        
    await graph.aupdate_state(config, update)
    
    # 5. Re-invoke graph seamlessly (None continues from current state)
    asyncio.create_task(graph.ainvoke(None, config=config))
    
    return {"status": "resumed", "action": request.action}
