#!/usr/bin/env python
"""
make_db.py - Create vector database from scraped data

Usage:
    python retrieval/make_db.py
    python retrieval/make_db.py -v
    python retrieval/make_db.py -i data/pages_math.json data/pages_calendar.json
    python retrieval/make_db.py -o custom_db
"""

import argparse
from .chunker import chunk_json
from .vector_store import create_vector_db


def main():
    parser = argparse.ArgumentParser(
        description="Create vector database from scraped JSON data"
    )
    parser.add_argument(
        "-i", "--input",
        nargs="+",
        default=["data/pages_math.json", "data/pages_calendar.json", "data/pages_synthetic.json"],
        help="One or more input JSON files",
    )
    parser.add_argument(
        "-o", "--output",
        default="db",
        help="Output vector database directory (default: db)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Show verbose output"
    )
    args = parser.parse_args()

    chunks = []
    for input_file in args.input:
        if args.verbose:
            print(f"Loading data from {input_file}...")
        file_chunks = chunk_json(input_file)
        chunks.extend(file_chunks)
        if args.verbose:
            print(f"  {len(file_chunks)} chunks from {input_file}")

    if args.verbose:
        print(f"Total: {len(chunks)} chunks")
        print("Rebuilding vector database (old DB cleared automatically)...")

    create_vector_db(chunks, args.output)
    print(f"Vector database rebuilt at {args.output}/")


if __name__ == "__main__":
    main()
