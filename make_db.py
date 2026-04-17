#!/usr/bin/env python
"""
make_db.py - Create vector database from scraped data

Usage:
    uv run python make_db.py
    uv run python make_db.py -v           # verbose output
    uv run python make_db.py --input custom.json --output custom_db
"""

import argparse
from chunker import chunk_json
from vector_store import create_vector_db


def main():
    parser = argparse.ArgumentParser(
        description="Create vector database from scraped JSON data"
    )
    parser.add_argument(
        "-i",
        "--input",
        default="data/pages.json",
        help="Input JSON file with scraped content (default: data/pages.json)",
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

    if args.verbose:
        print(f"Loading data from {args.input}...")

    # Load and chunk data
    chunks = chunk_json(args.input)

    if args.verbose:
        print(f"Loaded {len(chunks)} chunks from {args.input}")

    # Create vector database
    create_vector_db(chunks)

    print(f"Created vector database at {args.output}/")


if __name__ == "__main__":
    main()
