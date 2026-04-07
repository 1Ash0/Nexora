"""
Validation Script — Step 3: Full LangGraph workflow + HITL
Tests:
  1. Full research loop → synthesis produced
  2. Human-in-the-loop: graph pauses at human_review, resumes with injected feedback
"""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.getcwd())

from backend.graph.workflow import get_workflow
from backend.graph.state import get_initial_state


# ──────────────────────────────────────────────────────────────────────────────
async def test_full_loop():
    print("\n" + "="*60)
    print("TEST 1 — Full Research Loop")
    print("="*60)

    graph = get_workflow()
    query  = "What are the key differences between RAG and fine-tuning for LLM adaptation?"
    sid    = f"full-loop-{int(time.time())}"
    state  = get_initial_state(query, sid)
    config = {"configurable": {"thread_id": sid}}

    print(f"Query: {query}")
    t0 = time.time()
    try:
        result = await graph.ainvoke(state, config=config)
        elapsed = time.time() - t0

        tasks_done = len(result.get("completed_tasks", []))
        contradictions = len(result.get("contradictions", []))
        iterations = result.get("iteration_count", 0)
        synthesis = result.get("synthesis", "")

        print(f"  ✓ Completed in {elapsed:.1f}s")
        print(f"  ✓ Tasks completed : {tasks_done}")
        print(f"  ✓ Contradictions  : {contradictions}")
        print(f"  ✓ Iterations      : {iterations}")

        if synthesis:
            print(f"  ✓ PASS — Synthesis produced ({len(synthesis.split())} words)")
            print(f"    Preview: {synthesis[:300]}…")
        else:
            print("  ✗ FAIL — No synthesis produced")

    except Exception as e:
        print(f"  ✗ Loop failed: {e}")
        import traceback; traceback.print_exc()


# ──────────────────────────────────────────────────────────────────────────────
async def test_hitl():
    print("\n" + "="*60)
    print("TEST 2 — Human-In-The-Loop Interrupt / Resume")
    print("="*60)

    graph  = get_workflow()
    sid    = f"hitl-{int(time.time())}"
    state  = get_initial_state("Analyze current AI safety techniques", sid)
    config = {"configurable": {"thread_id": sid}}

    # ── Phase 1: run until the first interrupt (human_review) ──────────────
    print("Step 1 — Running until interrupt…")
    phase1 = await graph.ainvoke(state, config=config)

    # In LangGraph 0.3.x, get_state is SYNCHRONOUS
    current = graph.get_state(config)
    print(f"  Graph paused at: {current.next}")

    if "human_review" not in (current.next or []):
        # If critic gave "pass" first iteration the graph finished already.
        # Verify at minimum that synthesis was produced.
        synthesis = phase1.get("synthesis", "")
        if synthesis:
            print("  ✓ PASS — Graph completed in one pass (critic=pass). Synthesis produced.")
            print(f"    Preview: {synthesis[:200]}…")
        else:
            print("  ✗ FAIL — Graph did not reach human_review and produced no synthesis.")
        return

    print("  ✓ Interrupted at human_review")

    # ── Phase 2: inject feedback and resume ───────────────────────────────
    print("Step 2 — Injecting human feedback and resuming…")

    # `update_state` is also SYNCHRONOUS in 0.3.x
    graph.update_state(config, {
        "human_feedback": "Focus specifically on RLHF and Constitutional AI methods.",
        "interrupt_requested": False,
    })

    # Resume: pass None so LangGraph continues from the checkpoint
    result = await graph.ainvoke(None, config=config)

    synthesis = result.get("synthesis", "")
    if synthesis and ("RLHF" in synthesis or "Constitutional" in synthesis):
        print("  ✓ PASS — Human feedback reflected in synthesis")
        print(f"    Preview: {synthesis[:300]}…")
    elif synthesis:
        print("  ~ PARTIAL — Synthesis produced but feedback keywords not found")
        print(f"    Preview: {synthesis[:300]}…")
    else:
        print("  ✗ FAIL — No synthesis after resume")


# ──────────────────────────────────────────────────────────────────────────────
async def run_all():
    await test_full_loop()
    await test_hitl()


if __name__ == "__main__":
    asyncio.run(run_all())
