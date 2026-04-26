"""Quick smoke test for RAGAS with 3 questions before running the full eval."""
import os
import sys
import warnings
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import instructor
import anthropic
from ragas.llms import base as _ragas_llms_base

# Anthropic rejects requests with both temperature and top_p set.
_orig_map = _ragas_llms_base.InstructorLLM._map_provider_params
def _fixed_map(self):
    if self.provider.lower() == "anthropic":
        return {"temperature": self.model_args["temperature"], "max_tokens": self.model_args["max_tokens"]}
    return _orig_map(self)
_ragas_llms_base.InstructorLLM._map_provider_params = _fixed_map

import retrieval.embeddings as _emb
import chatbot_graph as _cg
from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy
from ragas.metrics.collections.context_relevance import ContextRelevance
from ragas.llms import LangchainLLMWrapper, InstructorLLM
from datasets import Dataset
from langchain_anthropic import ChatAnthropic

TEST_Q = [
    "What are the prerequisites for MATH 209?",
    "What is the Decima Robinson Support Centre?",
    "What are the requirements for honors math?",
]

_emb.EMBEDDING_PROVIDER = "ollama"
_emb._embeddings = None
_cg.LLM_PROVIDER = "claude"
_cg.DB_PATH = "ollama_db"
_cg._graph = None

graph = _cg._build_graph()

questions, answers, contexts = [], [], []

for q in TEST_Q:
    print(f"Running: {q}")
    result = graph.invoke({
        "question": q, "query_type": "", "refined_query": q,
        "context": "", "course_info": "", "chat_history": "No previous conversation.",
        "answer": "", "attempts": 0,
    })
    ctx = [c for c in result["context"].split("\n\n") if c.strip()]
    if result["course_info"] and "No specific course" not in result["course_info"]:
        ctx.insert(0, result["course_info"])
    if not ctx:
        ctx = ["No context retrieved."]

    questions.append(q)
    answers.append(result["answer"])
    contexts.append(ctx)
    print(f"  Answer preview: {result['answer'][:80]}")
    print()

JUDGE_MODEL = "claude-haiku-4-5-20251001"

print("Setting up RAGAS judges...")
lc_judge = LangchainLLMWrapper(ChatAnthropic(model=JUDGE_MODEL, temperature=0))
faithfulness.llm = lc_judge
answer_relevancy.llm = lc_judge

instr_client = instructor.from_anthropic(anthropic.AsyncAnthropic())
instr_llm = InstructorLLM(client=instr_client, model=JUDGE_MODEL, provider="anthropic")
cr_metric = ContextRelevance(llm=instr_llm)

print("Scoring faithfulness + answer_relevancy...")
dataset = Dataset.from_dict({"question": questions, "answer": answers, "contexts": contexts})
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    result = evaluate(dataset, metrics=[faithfulness, answer_relevancy])
df = result.to_pandas()

print("Scoring context_relevance...")
for i, (q, ctx) in enumerate(zip(questions, contexts)):
    try:
        cr = asyncio.run(cr_metric.ascore(user_input=q, retrieved_contexts=ctx))
        cr_val = cr.value if hasattr(cr, "value") else float(cr)
    except Exception as e:
        print(f"  CR error row {i}: {e}")
        cr_val = None
    df.loc[i, "context_relevance"] = cr_val

print()
print(df[["context_relevance", "faithfulness", "answer_relevancy"]].to_string())
