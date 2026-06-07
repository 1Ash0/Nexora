import json
import logging
import asyncio
from collections import defaultdict, deque
from typing import Any, Dict, Optional, List
from datetime import datetime
import redis.asyncio as aioredis
from backend.config.settings import settings

# In-memory event bus fallback (used when Redis is unavailable)
_memory_streams: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
_memory_listeners: dict[str, list] = defaultdict(list)
_use_redis = True  # auto-detected on first use

# Singleton Redis client — created once, reused for all events
_redis_client: Optional[aioredis.Redis] = None

async def _get_redis() -> aioredis.Redis:
    """Return the shared Redis client, creating it on first call."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_keepalive=True,
            socket_connect_timeout=3,
            retry_on_timeout=True,
        )
    return _redis_client

# Rich for terminal progress bars
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.live import Live
from langchain_core.callbacks import BaseCallbackHandler

import structlog
logger = structlog.get_logger("nexora.reporting")
console = Console()


class AgentCallbackHandler(BaseCallbackHandler):
    """LangChain callback to stream reasoning steps and tool calls."""

    def __init__(self, session_id: str, agent_name: str):
        self.session_id = session_id
        self.agent_name = agent_name

    async def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> Any:
        await report_event(
            self.session_id, self.agent_name, "thinking", "Analyzing complexity...",
            payload={"prompt_preview": prompts[0][:100] + "..." if prompts else ""}
        )

    async def on_chain_start(self, serialized: Dict[str, Any], inputs: Dict[str, Any], **kwargs: Any) -> Any:
        if serialized is None:
            return
        chain_name = serialized.get("name", "Process")
        await report_event(self.session_id, self.agent_name, "thinking", f"Starting {chain_name} chain...")

    async def on_tool_start(self, serialized: Dict[str, Any], input_str: str, **kwargs: Any) -> Any:
        tool_name = serialized.get("name", "Unknown Tool")
        await report_event(
            self.session_id, self.agent_name, "executing", f"Using tool: {tool_name}",
            payload={"query": input_str}
        )

    async def on_tool_end(self, output: str, **kwargs: Any) -> Any:
        await report_event(
            self.session_id, self.agent_name, "executing", "Tool execution completed.",
            payload={"output_snippet": output[:200] + "..." if len(output) > 200 else output}
        )


async def report_event(
    session_id: str,
    agent: str,
    status: str,
    action: str,
    payload: Optional[Dict[str, Any]] = None,
    emit_to_redis: bool = True
):
    """Centralized reporting for both terminal and frontend SSE stream."""
    timestamp = datetime.now().isoformat()
    p = payload or {}

    # Determine SSE event type
    if p.get("type") == "synthesis_complete":
        sse_type = "synthesis_complete"
    elif status == "error":
        sse_type = "error"
    elif p.get("type") == "task_update":
        sse_type = "task_update"
    elif p.get("type") == "sources_found":
        sse_type = "sources_found"
    elif p.get("type") == "refined_query":
        sse_type = "refined_query"
    else:
        sse_type = "agent_step"

    event = {
        "type": sse_type,
        "agent": agent,
        "status": status,
        "action": action,
        "payload": p,
        "timestamp": timestamp,
    }

    # Terminal output
    try:
        color = "blue" if "plan" in agent.lower() else "green" if "exec" in agent.lower() else "magenta"
        console.log(f"[{color}][{agent.upper()}][/] [bold]{status.upper()}[/]: {action}")
    except Exception:
        pass

    if not emit_to_redis:
        return

    global _use_redis
    if _use_redis:
        try:
            client = await _get_redis()
            event_id = await client.incr(f"session:{session_id}:event_counter")
            event["id"] = event_id
            await client.xadd(
                f"session:{session_id}:stream",
                {"data": json.dumps(event)},
                id="*",
            )
            await client.publish(f"session:{session_id}:events", json.dumps(event))
            return
        except Exception as e:
            logger.warning(f"Redis write failed, switching to in-memory: {e}")
            _use_redis = False
            _redis_client = None   # reset so it tries to reconnect next startup

    # In-memory fallback
    _memory_streams[session_id].append(event)
    for q in list(_memory_listeners[session_id]):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass


def get_memory_stream_events(session_id: str) -> list:
    return list(_memory_streams[session_id])


def subscribe_memory_stream(session_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=500)
    _memory_listeners[session_id].append(q)
    return q


def unsubscribe_memory_stream(session_id: str, q: asyncio.Queue):
    try:
        _memory_listeners[session_id].remove(q)
    except ValueError:
        pass


async def report_thought(session_id: str, agent: str, thought: str):
    await report_event(
        session_id=session_id,
        agent=agent,
        status="thinking",
        action="Processing reasoning step...",
        payload={"thought": thought},
    )
