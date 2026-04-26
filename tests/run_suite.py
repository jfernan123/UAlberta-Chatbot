"""
Run the test suite and save results to a Jupyter notebook.

Usage:
    python tests/run_suite.py
    python tests/run_suite.py --provider ollama
    python tests/run_suite.py --embedding sentence --db sentence_db
Output: tests/results/results_<timestamp>.ipynb
"""

import os
import sys
import json
import time
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_suite import EASY, MEDIUM, HARD
from chatbot_graph import build_chatbot, LLM_PROVIDER as CHATBOT_LLM_PROVIDER
import retrieval.embeddings as emb_module

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def make_markdown_cell(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source}


def build_notebook(runs: list[dict], elapsed: float, provider: str, embedding: str, db: str) -> dict:
    cells = []

    # Capture current configuration at runtime
    from chatbot_graph import _get_llm
    from retrieval.embeddings import get_embeddings

    # Get LLM model
    llm = _get_llm()
    llm_model = getattr(llm, "model", "N/A")

    # Get embedding model
    emb = get_embeddings()
    emb_model = getattr(emb, "model", "N/A")

    # Determine DB path
    db_path = "db/" if os.path.exists("db/chroma.sqlite3") else "N/A"

    # Header with configuration
    cells.append(
        make_markdown_cell(
            f"# Chatbot Test Suite Results\n\n"
            f"- **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
            f"- **LLM Provider:** {CHATBOT_LLM_PROVIDER}\n"
            f"- **LLM Model:** {llm_model}\n"
            f"- **Embedding Provider:** {emb_module.EMBEDDING_PROVIDER}\n"
            f"- **Embedding Model:** {emb_model}\n"
            f"- **DB Path:** {db_path}\n"
            f"- **Questions:** {len(runs)}\n"
            f"- **Total time:** {elapsed:.1f}s\n"
        )
    )

    current_category = None
    for run in runs:
        if run["category"] != current_category:
            current_category = run["category"]
            count = sum(1 for r in runs if r["category"] == current_category)
            cells.append(
                make_markdown_cell(f"---\n\n## {current_category} ({count} questions)")
            )

        # Q&A cell
        cells.append(
            make_markdown_cell(
                f"### Q{run['index']}: {run['question']}\n\n"
                f"**Time:** {run['elapsed']:.1f}s\n\n"
                f"---\n\n"
                f"{run['answer']}"
            )
        )

    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.11.0"},
        },
        "cells": cells,
    }


def main():
    parser = argparse.ArgumentParser(description="Run test suite and save to notebook")
    parser.add_argument("--provider", choices=["claude", "ollama"], default=None,
                        help="LLM provider (overrides LLM_PROVIDER env var)")
    parser.add_argument("--embedding", choices=["ollama", "sentence", "openai"], default=None,
                        help="Embedding provider (overrides EMBEDDING_PROVIDER env var)")
    parser.add_argument("--db", default=None,
                        help="Vector DB path (default: db)")
    args = parser.parse_args()

    import retrieval.embeddings as _emb
    import chatbot_graph as _cg

    if args.provider:
        _cg.LLM_PROVIDER = args.provider
    if args.embedding:
        _emb.EMBEDDING_PROVIDER = args.embedding
        _emb._embeddings = None
    if args.db:
        _cg.DB_PATH = args.db

    provider = _cg.LLM_PROVIDER
    embedding = _emb.EMBEDDING_PROVIDER
    db = _cg.DB_PATH

    print(f"LLM: {provider} | Embedding: {embedding} | DB: {db}")
    print("Loading chatbot...")
    bot = _cg.build_chatbot()

    categories = [("EASY", EASY), ("MEDIUM", MEDIUM), ("HARD", HARD)]
    runs = []
    total_start = time.time()
    q_index = 1

    for category, questions in categories:
        print(f"\n── {category} ({len(questions)} questions) ──")
        for question in questions:
            print(f"  [{q_index:02d}] {question[:70]}")
            t0 = time.time()
            try:
                answer = bot(question)
            except Exception as e:
                answer = f"**ERROR:** {e}"
            elapsed = time.time() - t0

            runs.append(
                {
                    "index": q_index,
                    "category": category,
                    "question": question,
                    "answer": answer,
                    "elapsed": elapsed,
                }
            )
            print(f"       → {elapsed:.1f}s")
            q_index += 1

    total_elapsed = time.time() - total_start
    print(f"\nDone. {len(runs)} questions in {total_elapsed:.1f}s")

    notebook = build_notebook(runs, total_elapsed, provider, embedding, db)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(RESULTS_DIR, f"results_{timestamp}.ipynb")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(notebook, f, ensure_ascii=False, indent=1)

    print(f"Saved → {out_path}")


if __name__ == "__main__":
    main()
