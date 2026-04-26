"""Isolated debug script for ContextRelevance scoring only."""
import asyncio
import warnings
warnings.filterwarnings("ignore")

import instructor
import anthropic
from ragas.llms import base as _ragas_llms_base

# Fix 1: Anthropic rejects both temperature+top_p
_orig_map = _ragas_llms_base.InstructorLLM._map_provider_params
def _fixed_map(self):
    if self.provider.lower() == "anthropic":
        return {"temperature": self.model_args["temperature"], "max_tokens": self.model_args["max_tokens"]}
    return _orig_map(self)
_ragas_llms_base.InstructorLLM._map_provider_params = _fixed_map

from ragas.metrics.collections.context_relevance import ContextRelevance
from ragas.metrics.collections.context_relevance.metric import (
    ContextRelevanceInput, ContextRelevanceOutput
)
from ragas.llms import InstructorLLM

QUESTION = "What are the prerequisites for MATH 209?"
CONTEXTS = [
    "MATH 209: Calculus III. Prerequisites: MATH 115 or equivalent. "
    "Topics include multivariable calculus, partial derivatives, and multiple integrals."
]
JUDGE_MODEL = "claude-haiku-4-5-20251001"


async def main():
    client = instructor.from_anthropic(anthropic.AsyncAnthropic())
    llm = InstructorLLM(client=client, model=JUDGE_MODEL, provider="anthropic")
    cr = ContextRelevance(llm=llm)

    print("Calling ascore...")
    result = await cr.ascore(user_input=QUESTION, retrieved_contexts=CONTEXTS)
    print(f"  value  : {result.value}")
    print(f"  reason : {result.reason}")

asyncio.run(main())
