#!/usr/bin/env python
"""
make_db.py - Create vector database from scraped data

Usage:
    uv run python make_db.py
    uv run python make_db.py -v           # verbose output
    uv run python make_db.py --input custom.json --output custom_db
"""

import argparse
from .chunker import chunk_json
from .vector_store import create_vector_db


def main():
    parser = argparse.ArgumentParser(
        description="Create vector database from scraped JSON data"
    )
    parser.add_argument(
        "-i",
        "--input",
        nargs="+",
        default=["data/pages.json"],
        help="One or more input JSON files (default: data/pages_math.json)",
    )
    parser.add_argument(
        "-o",
        "--output",
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

    create_vector_db(chunks)

    print(f"Created vector database at {args.output}/")


if __name__ == "__main__":
    main()
