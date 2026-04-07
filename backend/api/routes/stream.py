import asyncio
import json
from typing import AsyncGenerator, Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
import redis.asyncio as redis
from backend.config.settings import settings

router = APIRouter()

async def _publish_event(session_id: str, event: Dict[str, Any]):
    """
    Helper to publish event to Redis Stream and Pub/Sub.
    Stream is used for persistence (replay), PubSub for real-time trigger.
    """
    client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        # 1. Increment event counter
        event_id = await client.incr(f"session:{session_id}:event_counter")
        event["id"] = event_id
        
        # 2. Add to Stream (XADD) for persistence
        await client.xadd(
            f"session:{session_id}:stream",
            {"data": json.dumps(event)},
            id=f"{event_id}-0" # D3 standard or auto-generated
        )
        
        # 3. Publish to Channel (optional if only using XREAD, but good for dual mode)
        await client.publish(f"session:{session_id}:events", json.dumps(event))
    finally:
        await client.close()

async def event_generator(session_id: str, request: Request, last_event_id: Optional[str] = None) -> AsyncGenerator[str, None]:
    client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    stream_key = f"session:{session_id}:stream"
    
    # Handle Reconnection (Last-Event-ID)
    # If last_event_id is '10', we want to read from '10' onwards.
    # In Redis XREAD, the ID is usually 'timestamp-seq'. 
    # Our IDs are 'count-0'.
    current_id = last_event_id if last_event_id else "0-0"
    
    try:
        while True:
            if await request.is_disconnected():
                break
                
            # Read from Stream with timeout (15s heartbeat)
            # BLOCK 15000: wait up to 15s for new messages
            messages = await client.xread({stream_key: current_id}, count=10, block=15000)
            
            if messages:
                for stream, data_list in messages:
                    for msg_id, payload in data_list:
                        event_data = payload["data"]
                        event = json.loads(event_data)
                        
                        yield f"id: {event.get('id', msg_id)}\ndata: {event_data}\n\n"
                        current_id = msg_id
                        
                        # Stop if research complete
                        if event.get("type") == "synthesis_complete":
                            return
            else:
                # Heartbeat
                yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'detail': str(e)})}\n\n"
    finally:
        await client.close()

@router.get("/stream/{session_id}")
async def stream_session_events(session_id: str, request: Request):
    last_event_id = request.headers.get("Last-Event-ID")
    
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no", # For Nginx
    }
    
    return StreamingResponse(
        event_generator(session_id, request, last_event_id),
        media_type="text/event-stream",
        headers=headers
    )
