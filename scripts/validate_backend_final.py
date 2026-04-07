# scripts/validate_backend_final.py
import sys
import os
import asyncio
import uuid
import traceback

sys.path.append(os.getcwd())

from backend.graph.state import get_initial_state
from backend.agents.planner import PlannerAgent
from backend.agents.executor import ExecutorAgent
from backend.graph.workflow import get_workflow
from backend.memory.vector_store import VectorMemory
from backend.config.settings import settings
from backend.llm import create_chat_model


async def validate_planner():
    print("\n--- Section 2: PlannerAgent Validation ---")
    llm = create_chat_model(temperature=0.0)
    planner = PlannerAgent(llm=llm, settings=settings)
    state = get_initial_state("Compare transformer vs LSTM for time series forecasting", "s1")

    result = planner.plan(state)
    tasks = result["task_graph"]

    if 3 <= len(tasks) <= 7:
        print(f"PASS: {len(tasks)} tasks generated")
    else:
        print(f"FAIL: {len(tasks)} tasks generated")
        return False

    task_ids = {t["id"] for t in tasks}
    for t in tasks:
        for dep in t["dependencies"]:
            if dep not in task_ids:
                print(f"FAIL: Task {t['id']} has unknown dependency {dep}")
                return False
    print("PASS: No unknown dependencies")
    return True


async def validate_executor_dedup():
    print("\n--- Section 3: ExecutorAgent Deduplication ---")
    llm = create_chat_model(temperature=0.0)
    vm = VectorMemory(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    exec_agent = ExecutorAgent(llm=llm, tools=[], vector_memory=vm, settings=settings)

    session_id = f"dedup-test-{uuid.uuid4().hex[:8]}"
    metadata = {"session_id": session_id}
    chunks = ["The CEO of NVIDIA is Jensen Huang."]

    exec_agent._dedup_and_store(chunks, metadata)
    count1 = await vm.count_points(exec_agent.collection_name, session_id=session_id)

    exec_agent._dedup_and_store(chunks, metadata)
    count2 = await vm.count_points(exec_agent.collection_name, session_id=session_id)

    if count1 == 1 and count2 == 1:
        print(f"PASS: Deduplication works ({count1} points)")
    else:
        print(f"FAIL: Deduplication leaked! ({count1} -> {count2})")
        return False
    return True


async def validate_hitl():
    print("\n--- Section 5: HITL Interrupt + Resume ---")
    workflow = get_workflow()
    session_id = f"hitl-test-{uuid.uuid4().hex[:8]}"
    state = get_initial_state("AI alignment techniques", session_id)
    state["interrupt_requested"] = True
    config = {"configurable": {"thread_id": session_id}}

    print("Step 1: Starting research...")
    try:
        async for event in workflow.astream(state, config=config, stream_mode="updates"):
            node_name = list(event.keys())[0]
            print(f"  Node complete: {node_name}")

        snapshot = workflow.get_state(config)
        if snapshot is None:
            print("FAIL: No state snapshot found for session.")
            return False

        print(f"Current Next: {snapshot.next}")

        if any("human_review" in n for n in snapshot.next):
            print("PASS: System interrupted correctly.")

            print("Step 2: Resuming with feedback...")
            workflow.update_state(config, {
                "interrupt_requested": False,
                "human_feedback": "Focus on RLHF and Constitutional AI"
            })

            final_result = await workflow.ainvoke(None, config=config)
            if final_result.get("synthesis"):
                print("PASS: Synthesis successful after resume.")
                return True
            else:
                print("FAIL: No synthesis produced.")
                return False
        else:
            print(f"FAIL: Graph did not pause at human_review. Stopped at: {snapshot.next}")
            return False

    except Exception as e:
        print(f"HITL Validation CRASHED: {e}")
        traceback.print_exc()
        return False


async def main():
    s2 = await validate_planner()
    s3 = await validate_executor_dedup()
    s5 = await validate_hitl()

    if s2 and s3 and s5:
        print("\nGLOBAL BACKEND VALIDATION PASSED")
    else:
        print("\nGLOBAL BACKEND VALIDATION FAILED")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

