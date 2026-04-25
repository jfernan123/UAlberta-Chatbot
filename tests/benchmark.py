"""
Benchmark every LLM x embedding combination against the test suite.

Combinations:
    claude  x ollama    (ollama_db)
    claude  x sentence  (sentence_db)
    claude  x openai    (openai_db)
    ollama  x ollama    (ollama_db)
    ollama  x sentence  (sentence_db)
    ollama  x openai    (openai_db)

Usage:
    python tests/benchmark.py                        # all combinations
    python tests/benchmark.py --llm claude           # only claude combinations
    python tests/benchmark.py --llm ollama           # only ollama combinations
    python tests/benchmark.py --skip-embedding openai sentence  # skip embeddings
    python tests/benchmark.py --skip-llm ollama      # skip ollama LLM

Output: tests/results/benchmark_<timestamp>.ipynb
"""
import os
import sys
import json
import time
import argparse
from datetime import datetime
from itertools import product

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_suite import EASY, MEDIUM, HARD, TEST_QUESTIONS

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

ALL_LLMS = ["claude", "ollama"]
ALL_EMBEDDINGS = [
    {"name": "ollama",    "db": "ollama_db"},
    {"name": "sentence",  "db": "sentence_db"},
    {"name": "openai",    "db": "openai_db"},
]


def make_markdown_cell(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source}


def run_combo(llm: str, embedding: str, db: str) -> list[dict]:
    """Run all test questions for one LLM x embedding combo."""
    import retrieval.embeddings as _emb
    import chatbot_graph as _cg

    _emb.EMBEDDING_PROVIDER = embedding
    _emb._embeddings = None       # reset singleton
    _cg.LLM_PROVIDER = llm
    _cg.DB_PATH = db
    _cg._graph = None             # force rebuild with new settings

    bot = _cg.build_chatbot()
    results = []

    categories = [("EASY", EASY), ("MEDIUM", MEDIUM), ("HARD", HARD)]
    q_index = 1
    for category, questions in categories:
        for question in questions:
            t0 = time.time()
            try:
                answer = bot(question)
            except Exception as e:
                answer = f"**ERROR:** {e}"
            elapsed = time.time() - t0
            results.append({
                "index": q_index,
                "category": category,
                "question": question,
                "answer": answer,
                "elapsed": elapsed,
            })
            print(f"    [{q_index:02d}] {elapsed:.1f}s  {question[:55]}")
            q_index += 1

    return results


def build_notebook(all_runs: dict, total_elapsed: float) -> dict:
    cells = []

    combo_names = list(all_runs.keys())

    # Header
    cells.append(make_markdown_cell(
        f"# LLM × Embedding Benchmark\n\n"
        f"- **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"- **Combinations:** {len(combo_names)}\n"
        f"- **Questions per combo:** {len(TEST_QUESTIONS)}\n"
        f"- **Total time:** {total_elapsed:.1f}s\n"
    ))

    # Timing summary table
    rows = ["| LLM | Embedding | Total time | Avg/question |", "|---|---|---|---|"]
    for key, results in all_runs.items():
        llm, emb = key.split("|")
        total = sum(r["elapsed"] for r in results)
        avg = total / len(results) if results else 0
        rows.append(f"| {llm} | {emb} | {total:.1f}s | {avg:.1f}s |")
    cells.append(make_markdown_cell("## Timing Summary\n\n" + "\n".join(rows)))

    # Per-question comparison — one section per question, all combos stacked
    cells.append(make_markdown_cell("---\n\n## Results by Question"))

    n = len(TEST_QUESTIONS)
    current_category = None
    first_results = list(all_runs.values())[0]

    for i in range(n):
        category = first_results[i]["category"]
        if category != current_category:
            current_category = category
            count = sum(1 for r in first_results if r["category"] == category)
            cells.append(make_markdown_cell(f"---\n\n## {category} ({count} questions)"))

        question = first_results[i]["question"]
        parts = [f"### Q{i+1}: {question}\n"]

        for key, results in all_runs.items():
            llm, emb = key.split("|")
            r = results[i]
            parts.append(f"#### `{llm}` + `{emb}` — {r['elapsed']:.1f}s\n\n{r['answer']}\n")

        cells.append(make_markdown_cell("\n".join(parts)))

    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11.0"},
        },
        "cells": cells,
    }


def main():
    parser = argparse.ArgumentParser(description="Benchmark all LLM x embedding combinations")
    parser.add_argument("--llm", choices=["claude", "ollama"], default=None,
                        help="Run only this LLM (default: both)")
    parser.add_argument("--skip-llm", nargs="+", choices=["claude", "ollama"], default=[],
                        help="Skip these LLMs")
    parser.add_argument("--skip-embedding", nargs="+",
                        choices=["ollama", "sentence", "openai"], default=[],
                        help="Skip these embedding providers")
    args = parser.parse_args()

    llms = [args.llm] if args.llm else ALL_LLMS
    llms = [l for l in llms if l not in args.skip_llm]
    embeddings = [e for e in ALL_EMBEDDINGS if e["name"] not in args.skip_embedding]

    # Filter to combos where the DB exists
    combos = []
    for llm, emb in product(llms, embeddings):
        if not os.path.exists(emb["db"]):
            print(f"  SKIP: {llm} x {emb['name']} — {emb['db']} not found")
            continue
        combos.append((llm, emb))

    if not combos:
        print("No valid combinations found. Build DBs first with make_db.")
        return

    print(f"Running {len(combos)} combinations × {len(TEST_QUESTIONS)} questions\n")

    all_runs = {}
    total_start = time.time()

    for llm, emb in combos:
        key = f"{llm}|{emb['name']}"
        print(f"── {llm} x {emb['name']} ({emb['db']}) ──")
        all_runs[key] = run_combo(llm, emb["name"], emb["db"])
        print()

    total_elapsed = time.time() - total_start

    notebook = build_notebook(all_runs, total_elapsed)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(RESULTS_DIR, f"benchmark_{timestamp}.ipynb")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(notebook, f, ensure_ascii=False, indent=1)

    print(f"Done in {total_elapsed:.1f}s")
    print(f"Saved → {out_path}")


if __name__ == "__main__":
    main()
