import argparse
import re
import anthropic
from retrieval import load_retriever

# Set to True to print retrieved chunks before each answer
SHOW_CHUNKS = False

MODEL = "claude-haiku-4-5"
SYSTEM_PROMPT = """\
You are a helpful assistant for the University of Alberta Department of Mathematical and Statistical Sciences.
Answer questions using ONLY the context provided. Be concise and precise.
If the context does not contain enough information to answer, say so clearly — do not guess.
Always cite the source URL when you use information from a specific page.
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=10, help="Chunks to retrieve (default: 10)")
    args = parser.parse_args()

    print("Loading retriever...")
    retriever = load_retriever()
    retriever.search_kwargs["k"] = args.k

    client = anthropic.Anthropic()
    history = []
    print(f"Ready. Using {MODEL} with k={args.k}. Type 'quit' to exit.\n")

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            break

        if not question or question.lower() in ("quit", "exit"):
            break

        # Prepend course codes so BM25 matches exactly (e.g. STAT 471)
        course_codes = re.findall(r'\b([A-Z]{2,6})\s*(\d{3})\b', question.upper())
        query = question
        if course_codes:
            code_str = " ".join(f"{subj} {num}" for subj, num in course_codes)
            query = f"{code_str} {question}"

        docs = retriever.invoke(query)
        context = "\n\n".join(doc.page_content for doc in docs)

        if SHOW_CHUNKS:
            print(f"\n--- Retrieved {len(docs)} chunks ---")
            for i, doc in enumerate(docs, 1):
                print(f"\n[{i}] {doc.page_content}")
            print("\n" + "-" * 40)

        history.append({"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"})

        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=history,
        )

        answer = response.content[0].text
        history.append({"role": "assistant", "content": answer})

        print(f"\nAssistant: {answer}\n")


if __name__ == "__main__":
    main()
