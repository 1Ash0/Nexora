import argparse
import asyncio
import uuid
import structlog
from backend.graph.workflow import get_workflow
from backend.graph.state import ResearchState
import dotenv

dotenv.load_dotenv()
logger = structlog.get_logger()

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", type=str, required=True, help="Test query")
    args = parser.parse_args()

    session_id = f"test_{uuid.uuid4().hex[:8]}"
    workflow = get_workflow()
    
    initial_state = ResearchState(
        original_query=args.query,
        human_feedback="",
        iteration_count=0,
        task_graph=[],
        session_id=session_id
    )

    print(f"Starting test memory integration graph execution with query: {args.query}")
    
    config = {"configurable": {"thread_id": session_id}}
    
    async for event in workflow.astream(initial_state, config=config):
        for node_name, state in event.items():
            print(f"--- Completed Node: {node_name} ---")
            
    print("Graph execution finished.")

if __name__ == "__main__":
    asyncio.run(main())
