import asyncio
import os
import sys

# Add workspace to path
sys.path.insert(0, os.getcwd())

from backend.agents.contradiction_engine import ContradictionEngine
from backend.config.settings import settings
from backend.llm import create_chat_model


async def test_contradiction_types():
    llm = create_chat_model(temperature=0.0)
    engine = ContradictionEngine(llm=llm, settings=settings)

    test_cases = [
        {
            "claim_a": "GPT-4 achieves 94.3% accuracy on MMLU benchmark",
            "claim_b": "GPT-4 achieves 78.1% accuracy on MMLU benchmark",
            "expected_type": "direct",
            "source_a": "openai.com/paper", "source_b": "arxiv.org/abs/2305.xxxx"
        },
        {
            "claim_a": "Random forests outperform neural networks based on 10-fold CV on UCI datasets",
            "claim_b": "Neural networks significantly outperform random forests on the same UCI datasets (holdout evaluation)",
            "expected_type": "methodological",
            "source_a": "journal1.com", "source_b": "journal2.com"
        },
        {
            "claim_a": "Transformers are more efficient than LSTMs for sequence modeling",
            "claim_b": "LSTMs outperform Transformers on edge devices with < 512MB RAM",
            "expected_type": "scope",
            "source_a": "paper1.com", "source_b": "paper2.com"
        }
    ]

    print("\n--- Testing Contradiction Classification ---")
    for tc in test_cases:
        result = await engine._classify_pair(
            tc["claim_a"], tc["claim_b"], tc["source_a"], tc["source_b"]
        )
        got = result.get("type", "none")
        status = "PASS" if got == tc["expected_type"] else f"FAIL (got {got})"
        print(f"{status}: {tc['expected_type']} - {tc['claim_a'][:40]}")


if __name__ == "__main__":
    asyncio.run(test_contradiction_types())

