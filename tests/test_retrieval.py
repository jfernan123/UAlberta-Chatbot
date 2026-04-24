"""
test_retrieval.py

Tests the vector DB retrieval in isolation — no LLM involved.
Prints the top-k chunks returned for each query so you can judge
whether the right content is being fetched before touching the chatbot.

Usage:
    python test_retrieval.py
    python test_retrieval.py --k 6
    python test_retrieval.py --query "admission requirements for grad school"
"""

import argparse
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from retrieval import load_retriever

DEFAULT_QUERIES = [
    "what are the prerequisites for STAT 371",
    "how do I apply to the MSc statistics program",
    "what courses are required for honors in statistics",
    "who are the faculty members in the department",
    "what is the tuition fee for graduate students",
]


def test(queries: list[str], k: int) -> None:
    print("Loading retriever...")
    retriever = load_retriever()
    retriever.search_kwargs["k"] = k
    print(f"Retriever loaded. Testing {len(queries)} queries with k={k}.\n")

    for query in queries:
        print("=" * 70)
        print(f"QUERY: {query}")
        print("=" * 70)
        docs = retriever.invoke(query)
        if not docs:
            print("  (no results)")
        for i, doc in enumerate(docs, start=1):
            print(f"\n  [chunk {i}]")
            print(f"  {doc.page_content[:400]}")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Test vector DB retrieval.")
    parser.add_argument("--query", default=None, help="Single query to test.")
    parser.add_argument("--k", type=int, default=4, help="Number of chunks to retrieve (default: 4).")
    args = parser.parse_args()

    queries = [args.query] if args.query else DEFAULT_QUERIES
    test(queries, args.k)


if __name__ == "__main__":
    main()
