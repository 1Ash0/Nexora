"""
Validation Script - Step 1: ExecutorAgent
Tests:
  1. Deduplication: second run with same task does NOT add new Qdrant points
  2. Tool failure: returns graceful error result, does not crash
"""

import asyncio
import os
import sys
import unittest.mock as mock

sys.path.insert(0, os.getcwd())

from backend.agents.executor import ExecutorAgent
from backend.memory.vector_store import VectorMemory
from backend.graph.state import TaskItem, get_initial_state
from backend.config.settings import settings
from backend.tools import EXECUTOR_TOOLS
from backend.llm import create_chat_model


async def test_executor_dedup():
    print("\n" + "=" * 60)
    print("TEST 1 - ExecutorAgent Deduplication")
    print("=" * 60)

    llm = create_chat_model(temperature=0.0)
    vm = VectorMemory(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    agent = ExecutorAgent(llm=llm, tools=EXECUTOR_TOOLS, vector_memory=vm, settings=settings)

    session_id = f"dedup-test-{int(__import__('time').time())}"
    task = TaskItem(
        id="t1",
        description="Find current CEO of NVIDIA",
        status="pending", priority=1, dependencies=[], result=None, confidence=0.0,
    )
    state = get_initial_state("Who is NVIDIA CEO", session_id)

    print("First execution...")
    result1 = await agent.execute(task, state)
    count1 = await vm.count_points(agent.collection_name, session_id=session_id)
    print(f"  Points after first run : {count1}")
    print(f"  Task status            : {result1['completed_tasks'][0]['status']}")

    task.status = "pending"
    task.result = None

    print("Second execution (retry simulation)...")
    await agent.execute(task, state)
    count2 = await vm.count_points(agent.collection_name, session_id=session_id)
    print(f"  Points after second run: {count2}")

    if count2 == count1:
        print(f"  ? PASS - Deduplication works ({count1} unique chunks stored)")
    else:
        print(f"  ? FAIL - Duplicates created ({count1} ? {count2})")


async def test_executor_tool_failure():
    print("\n" + "=" * 60)
    print("TEST 2 - ExecutorAgent Graceful Tool Failure")
    print("=" * 60)

    llm = create_chat_model(temperature=0.0)
    vm = VectorMemory(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    agent = ExecutorAgent(llm=llm, tools=EXECUTOR_TOOLS, vector_memory=vm, settings=settings)

    task = TaskItem(
        id="t-fail",
        description="Search for information",
        status="pending", priority=1, dependencies=[], result=None, confidence=0.0,
    )
    state = get_initial_state("Failure test", "fail-test")

    patched_tools = []
    for t in EXECUTOR_TOOLS:
        m = mock.MagicMock()
        m.name = t.name
        m.description = getattr(t, "description", "")
        m.args_schema = getattr(t, "args_schema", None)
        m.run = mock.MagicMock(side_effect=Exception("Simulated tool failure"))
        m.arun = mock.AsyncMock(side_effect=Exception("Simulated tool failure"))
        patched_tools.append(m)

    agent.tools = patched_tools

    result = await agent.execute(task, state)
    status = result["completed_tasks"][0]["status"]
    if status in ("failed", "done"):
        print(f"  ? PASS - Agent handled failure gracefully (status={status})")
    else:
        print(f"  ? FAIL - Unexpected status: {status}")


async def run_all():
    try:
        await test_executor_dedup()
    except Exception as e:
        print(f"  ? Dedup test exception: {e}")
        import traceback; traceback.print_exc()

    try:
        await test_executor_tool_failure()
    except Exception as e:
        print(f"  ? Failure-handling test exception: {e}")
        import traceback; traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all())

