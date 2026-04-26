"""
RAGAS evaluation script (compatible with RAGAS 0.4.x).

Runs all 46 test questions through each LLM x embedding combination,
captures (question, answer, retrieved context), and scores with RAGAS:
  - Context Relevance  : is the retrieved context useful for the question?
  - Faithfulness       : is the answer grounded in the retrieved context?
  - Answer Relevancy   : does the answer actually address the question?

Usage:
    python tests/ragas_eval.py
    python tests/ragas_eval.py --llm claude
    python tests/ragas_eval.py --skip-embedding openai

Output:
    tests/results/ragas_captures/    checkpointed captures per combo (JSON)
    tests/results/ragas_raw.csv      per-question scores
    tests/results/ragas_summary.csv  mean scores per combination
"""
import os
import sys
import json
import csv
import argparse
import time
import warnings
import asyncio
from itertools import product

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import retrieval.embeddings as _emb
import chatbot_graph as _cg
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

from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy
from ragas.metrics.collections.context_relevance import ContextRelevance
from ragas.llms import LangchainLLMWrapper, InstructorLLM
from datasets import Dataset
from langchain_anthropic import ChatAnthropic
from tests.test_suite import TEST_QUESTIONS, EASY, MEDIUM, HARD

RESULTS_DIR  = os.path.join(os.path.dirname(__file__), "results")
CAPTURES_DIR = os.path.join(RESULTS_DIR, "ragas_captures")
os.makedirs(RESULTS_DIR,  exist_ok=True)
os.makedirs(CAPTURES_DIR, exist_ok=True)

ALL_LLMS = ["claude", "ollama"]
ALL_EMBEDDINGS = [
    {"name": "ollama",   "db": "ollama_db"},
    {"name": "sentence", "db": "sentence_db"},
    {"name": "openai",   "db": "openai_db"},
]

TIER_MAP = {}
for q in EASY:   TIER_MAP[q] = "Easy"
for q in MEDIUM: TIER_MAP[q] = "Medium"
for q in HARD:   TIER_MAP[q] = "Hard"

JUDGE_MODEL = "claude-haiku-4-5-20251001"


def _make_judge():
    """LangchainLLMWrapper for faithfulness + answer_relevancy (old singleton API)."""
    return LangchainLLMWrapper(ChatAnthropic(model=JUDGE_MODEL, temperature=0))


def _make_cr_metric():
    """InstructorLLM-backed ContextRelevance for the new-API metric."""
    client = instructor.from_anthropic(anthropic.AsyncAnthropic())
    llm = InstructorLLM(client=client, model=JUDGE_MODEL, provider="anthropic")
    return ContextRelevance(llm=llm)


# --------------------------------------------------------------------------- #
# Checkpoint helpers                                                            #
# --------------------------------------------------------------------------- #
def _checkpoint_path(key):
    safe = key.replace(" ", "_").replace("+", "plus")
    return os.path.join(CAPTURES_DIR, f"{safe}.json")


def _save_checkpoint(key, records):
    with open(_checkpoint_path(key), "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=1)
    print(f"  Checkpoint saved -> {_checkpoint_path(key)}")


def _load_checkpoint(key):
    path = _checkpoint_path(key)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return None


# --------------------------------------------------------------------------- #
# Step 1: run chatbot and capture contexts                                      #
# --------------------------------------------------------------------------- #
def run_and_capture(llm, embedding, db):
    _emb.EMBEDDING_PROVIDER = embedding
    _emb._embeddings = None
    _cg.LLM_PROVIDER = llm
    _cg.DB_PATH = db
    _cg._graph = None

    graph = _cg._build_graph()
    records = []

    for i, question in enumerate(TEST_QUESTIONS, 1):
        t0 = time.time()
        try:
            initial_state = {
                "question":      question,
                "query_type":    "",
                "refined_query": question,
                "context":       "",
                "course_info":   "",
                "chat_history":  "No previous conversation.",
                "answer":        "",
                "attempts":      0,
            }
            result = graph.invoke(initial_state)
            answer = result["answer"]

            contexts = [c for c in result["context"].split("\n\n") if c.strip()]
            if result["course_info"] and "No specific course" not in result["course_info"]:
                contexts.insert(0, result["course_info"])
            if not contexts:
                contexts = ["No context retrieved."]

        except Exception as e:
            answer = f"ERROR: {e}"
            contexts = ["No context retrieved."]

        elapsed = time.time() - t0
        records.append({
            "question": question,
            "tier":     TIER_MAP.get(question, "Unknown"),
            "answer":   answer,
            "contexts": contexts,
            "elapsed":  round(elapsed, 2),
        })
        print(f"  [{i:02d}] {elapsed:.1f}s  {question[:55]}")

    return records


# --------------------------------------------------------------------------- #
# Step 2: score with RAGAS 0.4.x                                               #
# --------------------------------------------------------------------------- #
def score_with_ragas(records):
    print("  Setting up RAGAS judge...")
    judge = _make_judge()
    faithfulness.llm = judge
    answer_relevancy.llm = judge

    cr_metric = _make_cr_metric()

    dataset = Dataset.from_dict({
        "question": [r["question"] for r in records],
        "answer":   [r["answer"]   for r in records],
        "contexts": [r["contexts"] for r in records],
    })

    print("  Scoring faithfulness + answer_relevancy...")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result = evaluate(dataset, metrics=[faithfulness, answer_relevancy],
                          batch_size=2, raise_exceptions=False)
    result_df = result.to_pandas()

    print("  Scoring context_relevance...")
    cr_scores = []
    for r in records:
        time.sleep(1.5)
        try:
            cr_result = asyncio.run(cr_metric.ascore(
                user_input=r["question"],
                retrieved_contexts=r["contexts"],
            ))
            cr_scores.append(cr_result.value if hasattr(cr_result, "value") else float(cr_result))
        except Exception as e:
            print(f"    CR score failed: {e}")
            cr_scores.append(None)

    scored = []
    for i, record in enumerate(records):
        scored.append({
            **record,
            "context_relevancy": cr_scores[i],
            "faithfulness":      result_df.iloc[i].get("faithfulness"),
            "answer_relevancy":  result_df.iloc[i].get("answer_relevancy"),
        })
    return scored


# --------------------------------------------------------------------------- #
# Main                                                                          #
# --------------------------------------------------------------------------- #
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", choices=["claude", "ollama"], default=None)
    parser.add_argument("--skip-embedding", nargs="+",
                        choices=["ollama", "sentence", "openai"], default=[])
    args = parser.parse_args()

    llms       = [args.llm] if args.llm else ALL_LLMS
    embeddings = [e for e in ALL_EMBEDDINGS if e["name"] not in args.skip_embedding]

    combos = []
    for llm, emb in product(llms, embeddings):
        if not os.path.exists(emb["db"]):
            print(f"  SKIP: {llm} x {emb['name']} - {emb['db']} not found")
            continue
        combos.append((llm, emb))

    if not combos:
        print("No valid combinations found.")
        return

    print(f"Running {len(combos)} combinations x {len(TEST_QUESTIONS)} questions\n")

    all_scored   = []
    summary_rows = []

    for llm, emb in combos:
        key = f"{llm} + {emb['name']}"
        print(f"-- {key} --")

        cached = _load_checkpoint(key)
        if cached:
            print(f"  Loaded {len(cached)} records from checkpoint")
            records = cached
        else:
            records = run_and_capture(llm, emb["name"], emb["db"])
            _save_checkpoint(key, records)

        scored = score_with_ragas(records)

        for row in scored:
            all_scored.append({"combo": key, **row})

        valid_cr  = [r["context_relevancy"] for r in scored if r["context_relevancy"] is not None]
        valid_fth = [r["faithfulness"]      for r in scored if r["faithfulness"]      is not None]
        valid_ar  = [r["answer_relevancy"]  for r in scored if r["answer_relevancy"]  is not None]

        cr  = sum(valid_cr)  / len(valid_cr)  if valid_cr  else 0.0
        fth = sum(valid_fth) / len(valid_fth) if valid_fth else 0.0
        ar  = sum(valid_ar)  / len(valid_ar)  if valid_ar  else 0.0

        summary_rows.append({
            "combo":            key,
            "context_relevancy": round(cr,  3),
            "faithfulness":      round(fth, 3),
            "answer_relevancy":  round(ar,  3),
        })
        print(f"  CR={cr:.3f}  Faith={fth:.3f}  AR={ar:.3f}\n")

    raw_path = os.path.join(RESULTS_DIR, "ragas_raw.csv")
    with open(raw_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "combo", "tier", "question",
            "context_relevancy", "faithfulness", "answer_relevancy",
            "elapsed", "answer",
        ])
        writer.writeheader()
        for row in all_scored:
            writer.writerow({
                "combo":             row["combo"],
                "tier":              row["tier"],
                "question":          row["question"],
                "context_relevancy": row.get("context_relevancy", ""),
                "faithfulness":      row.get("faithfulness", ""),
                "answer_relevancy":  row.get("answer_relevancy", ""),
                "elapsed":           row["elapsed"],
                "answer":            row["answer"][:300],
            })
    print(f"Raw results -> {raw_path}")

    summary_path = os.path.join(RESULTS_DIR, "ragas_summary.csv")
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "combo", "context_relevancy", "faithfulness", "answer_relevancy"
        ])
        writer.writeheader()
        writer.writerows(summary_rows)
    print(f"Summary -> {summary_path}")

    print("\n=== RAGAS Summary ===")
    for row in summary_rows:
        print(f"  {row['combo']:<35} CR={row['context_relevancy']}  F={row['faithfulness']}  AR={row['answer_relevancy']}")


if __name__ == "__main__":
    main()
