"""
test_chatbot.py

Quick CLI chatbot using Claude Haiku + the vector DB retriever.
No Streamlit, no Ollama LLM — just retrieval + Claude in the terminal.

Usage:
    python test_chatbot.py
    python test_chatbot.py --k 6
"""

import argparse
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import anthropic
from retrieval import load_retriever

MODEL = "claude-haiku-4-5"
SYSTEM_PROMPT = """\
You are a helpful assistant for the University of Alberta Department of Mathematical and Statistical Sciences.
Answer questions using ONLY the context provided. Be concise and precise.
If the context does not contain enough information to answer, say so clearly — do not guess.
Always cite the source URL when you use information from a specific page.
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=6, help="Chunks to retrieve (default: 6)")
    args = parser.parse_args()

    print("Loading retriever...")
    retriever = load_retriever()
    retriever.search_kwargs["k"] = args.k

    client = anthropic.Anthropic()
    print(f"Ready. Using {MODEL} with k={args.k}. Type 'quit' to exit.\n")

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not question or question.lower() in ("quit", "exit"):
            break

        # If query mentions a course code (e.g. STAT 371), prepend it so BM25 matches exactly
        course_codes = re.findall(r'\b([A-Z]{2,6})\s*(\d{3})\b', question.upper())
        query = question
        if course_codes:
            code_str = " ".join(f"{subj} {num}" for subj, num in course_codes)
            query = f"{code_str} {question}"

        docs = retriever.invoke(query)
        context = "\n\n".join(doc.page_content for doc in docs)

        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
        )
        print(f"\nAssistant: {response.content[0].text}\n")


if __name__ == "__main__":
    main()
