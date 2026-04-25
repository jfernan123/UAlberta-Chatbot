#!/usr/bin/env python
"""
make_db.py - Delete and rebuild the vector database from scratch.

Usage:
    python -m retrieval.make_db                        # delete old DB and rebuild (ollama embeddings)
    python -m retrieval.make_db --embedding ollama     # nomic-embed-text via Ollama (default)
    python -m retrieval.make_db --embedding sentence   # BGE local via sentence-transformers
    python -m retrieval.make_db --embedding openai     # OpenAI text-embedding-3-small
    python -m retrieval.make_db -v                     # verbose — shows chunk counts per file

"""

import argparse
from .chunker import chunk_json
from .vector_store import create_vector_db


def main():
    parser = argparse.ArgumentParser(
        description="Delete and rebuild the Chroma vector database from scratch."
    )
    parser.add_argument(
        "-i", "--input",
        nargs="+",
        default=["data/pages_math.json", "data/pages_calendar.json", "data/pages_synthetic.json"],
        help="Input JSON files (default: the three filtered data files)",
    )
    parser.add_argument(
        "-o", "--output",
        default="db",
        help="Output directory for the vector DB (default: db)",
    )
    parser.add_argument(
        "--embedding",
        choices=["ollama", "sentence", "openai"],
        default=None,
        help="Embedding provider: ollama (nomic-embed-text), sentence (BGE), openai. Overrides EMBEDDING_PROVIDER env var.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show chunk counts per file",
    )
    args = parser.parse_args()

    # Apply embedding override before get_embeddings() is called
    if args.embedding:
        import retrieval.embeddings as _emb
        _emb.EMBEDDING_PROVIDER = args.embedding

    chunks = []
    for input_file in args.input:
        if args.verbose:
            print(f"Loading {input_file}...")
        file_chunks = chunk_json(input_file)
        chunks.extend(file_chunks)
        if args.verbose:
            print(f"  {len(file_chunks)} chunks")

    if args.verbose:
        print(f"Total: {len(chunks)} chunks")
        print(f"Deleting old DB and rebuilding...")

    create_vector_db(chunks, args.output)
    print(f"Done. Vector DB rebuilt at {args.output}/")


if __name__ == "__main__":
    main()
