# scripts/test_schema.py
import sys
import os
sys.path.append(os.getcwd())

from backend.graph.state import ResearchState, TaskItem, get_initial_state
from backend.graph.state import TaskItem as TaskItemModel
from langgraph.graph import StateGraph
import operator
from pydantic import ValidationError

def test_schema():
    print("--- Section 1: ResearchState Schema Validation ---")
    
    # Test 1: Initial state shape
    state = get_initial_state("Test query about AI", "session-001")
    expected_keys = {
        "session_id", "original_query", "refined_query", "task_graph",
        "completed_tasks", "contradictions", "sources", "synthesis",
        "iteration_count", "interrupt_requested", "human_feedback",
        "graph_nodes", "graph_edges", "error", "metadata"
    }
    actual_keys = set(state.keys())
    if actual_keys == expected_keys:
        print("PASS: Initial state shape is correct")
    else:
        print(f"FAIL: Missing keys: {expected_keys - actual_keys}")
        print(f"FAIL: Extra keys: {actual_keys - expected_keys}")

    # Test 2: Annotated list merge behavior
    try:
        graph = StateGraph(ResearchState)
        print("PASS: Schema compiles in StateGraph")
    except Exception as e:
        print(f"FAIL: Schema failed to compile in StateGraph: {e}")

    # Test 3: TaskItem Pydantic validation
    print("\nTest 3: TaskItem Pydantic validation")
    try:
        # Should fail due to invalid status and confidence > 1.0
        bad_task = TaskItemModel(
            id="t1", 
            description="test", 
            status="invalid_status", # Invalid Literal
            priority=1, 
            dependencies=[], 
            result=None, 
            confidence=1.5 # Should be <= 1.0
        )
        print("FAIL: Should have rejected invalid status and confidence > 1.0")
    except ValidationError as e:
        print(f"PASS: Validation correctly rejected invalid input: {e.error_count()} errors found")
    except Exception as e:
        print(f"FAIL: Unexpected error during validation: {type(e).__name__}: {e}")

    # Test 4: Valid TaskItem
    try:
        good_task = TaskItemModel(
            id="t1",
            description="valid task",
            status="pending",
            priority=1,
            dependencies=[],
            result=None,
            confidence=0.0
        )
        print("PASS: Valid TaskItem accepted")
    except Exception as e:
        print(f"FAIL: Good task rejected: {e}")

if __name__ == "__main__":
    test_schema()
