#!/usr/bin/env python
"""
filter_crawler.py - Filter web_crawler output for Math & Stats pages

Filters URLs by priority:
  1. /undergraduate-studies/programs/  (highest)
  2. /undergraduate-studies/courses/
  3. /graduate-studies/

Usage:
    uv run python filter_crawler.py --input-dir raw_html
    uv run python filter_crawler.py --input-dir raw_html --max-urls 30
"""

import argparse
import json
import os

from parsers import parse_html_to_sections


def score_url(url):
    """Score URL by priority. Lower is better."""
    if "/undergraduate-studies/programs/" in url:
        return 1
    elif "/undergraduate-studies/courses/" in url:
        return 2
    elif "/graduate-studies/" in url:
        return 3
    else:
        return 999  # Not in priority list


def filter_and_parse(input_dir, max_urls=None):
    """Filter and parse HTML files from web_crawler output."""
    manifest_path = os.path.join(input_dir, "manifest.json")

    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"manifest.json not found in {input_dir}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print(f"Found {len(manifest)} URLs in manifest")

    # Score all URLs
    scored = []
    for entry in manifest:
        url = entry.get("url", "")
        score = score_url(url)
        if score < 999:  # Keep only priority URLs
            scored.append((score, url, entry.get("file")))

    print(f"Priority URLs found: {len(scored)}")

    # Sort by score (priority) and limit
    scored.sort(key=lambda x: x[0])

    if max_urls:
        scored = scored[:max_urls]
        print(f"Limiting to {max_urls} URLs")

    # Parse HTML files
    results = []
    errors = []

    for i, (score, url, filename) in enumerate(scored, 1):
        filepath = os.path.join(input_dir, filename)

        if not os.path.exists(filepath):
            errors.append(f"File not found: {filepath}")
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                html = f.read()

            result = parse_html_to_sections(html, url)
            results.append(result)
            print(f"[{i}/{len(scored)}] Parsed: {url[:60]}...")

        except Exception as e:
            errors.append(f"Error parsing {filename}: {e}")

    if errors:
        print(f"\nErrors: {len(errors)}")
        for err in errors[:5]:
            print(f"  - {err}")

    print(f"\nProcessed {len(results)} pages")
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Filter web_crawler output for Math & Stats pages"
    )
    parser.add_argument(
        "--input-dir",
        default="raw_html",
        help="Input directory with manifest.json (default: raw_html)",
    )
    parser.add_argument(
        "--output",
        default="data/pages_filtered.json",
        help="Output JSON file (default: data/pages_filtered.json)",
    )
    parser.add_argument(
        "--max-urls",
        type=int,
        default=None,
        help="Maximum URLs to process (default: all priority URLs)",
    )
    args = parser.parse_args()

    print(f"Filtering: {args.input_dir}")
    print(
        f"Priority patterns: /undergraduate-studies/programs/, /undergraduate-studies/courses/, /graduate-studies/"
    )

    # Filter and parse
    results = filter_and_parse(args.input_dir, args.max_urls)

    # Save results
    os.makedirs(os.path.dirname(args.output) or "data", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    total_sections = sum(len(r.get("sections", [])) for r in results)
    print(f"\nSaved {len(results)} pages to {args.output}")
    print(f"Total sections: {total_sections}")


if __name__ == "__main__":
    main()
