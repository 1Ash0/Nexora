import asyncio
import os
import sys

# Add workspace to path
sys.path.insert(0, os.getcwd())

from backend.graph.workflow import get_workflow
from backend.graph.state import get_initial_state

async def main():
    print("Initializing graph...")
    graph = get_workflow()
    
    state = get_initial_state("Quick test", "test-1")
    config = {"configurable": {"thread_id": "test-1"}}
    
    print("Starting ainvoke...")
    try:
        await graph.ainvoke(state, config=config)
        print("Ainvoke returned.")
        
        current = await graph.get_state(config)
        print(f"Current next: {current.next}")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
