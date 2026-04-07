import os
import asyncio
from dotenv import load_dotenv
load_dotenv('.env')

from backend.graph.state import ResearchState, TaskItem, Contradiction
from backend.agents.synthesizer import SynthesizerAgent
from backend.config.settings import settings
from langchain_openai import ChatOpenAI

async def test_synthesis():
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        print("Skipping test: No OpenAI API key.")
        return

    # User requires temperature=0.3 for synthesis prose
    llm = ChatOpenAI(model=settings.OPENAI_MODEL, temperature=0.3, api_key=api_key)
    agent = SynthesizerAgent(llm, settings)

    state = {
        "original_query": "The impact of microplastics on human cardiovascular health",
        "refined_query": "Review of current research on microplastic presence in human arterial plaques and its correlation with cardiovascular events.",
        "completed_tasks": [
            {
                "id": "t1",
                "description": "Evidence of microplastics in arterial plaque",
                "status": "done",
                "result": "A 2024 study in the NEJM found microplastics and nanoplastics in the carotid artery plaque of 58% of 257 participants. Those with plaque containing plastics had a higher risk of heart attack, stroke, or death.",
                "confidence": 0.95
            },
            {
                "id": "t2",
                "description": "Alternative viewpoints or negative studies",
                "status": "done",
                "result": "Some researchers suggest that the presence of microplastics might be a marker of overall environmental exposure rather than a direct causative factor in plaque formation.",
                "confidence": 0.8
            }
        ],
        "contradictions": [
            {
                "id": "c1",
                "type": "direct",
                "severity": 0.7,
                "claim_a": "Microplastics directly cause arterial inflammation leading to plaque buildup.",
                "claim_b": "Microplastics are innocent bystanders trapped in existing plaque and do not contribute to inflammation."
            }
        ],
        "sources": [{"url": "https://nejm.org/example", "title": "NEJM Plaque Study"}],
        "human_feedback": "Please ensure the tone is cautious but informative."
    }

    print("\n--- STARTING SYNTHESIZER AGENT ---\n")
    result = agent.synthesize(state)
    
    print("\n--- SYNTHESIS COMPLETE ---\n")
    print(f"Report Summary (First 500 chars):\n{result['synthesis'][:500]}...")
    print(f"\nWord Count: {result['metadata']['word_count']}")
    print(f"Source Count: {result['metadata']['source_count']}")
    print(f"Confidence Summary: {result['metadata']['confidence_summary']}")
    print(f"Key Findings: {result['metadata']['key_findings']}")

if __name__ == '__main__':
    asyncio.run(test_synthesis())
