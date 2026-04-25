"""
merge_pages.py

Merges one or more pages JSON files into a base dataset, deduplicating by URL.
Existing entries in the base file are kept; new entries from --add are appended.

Usage:
    python scraping/merge_pages.py --add data/pages_extra.json --base data/pages_math.json
    python scraping/merge_pages.py --add data/pages_extra.json --base data/pages_math.json --dry-run
"""

import argparse
import json


def merge(base_path: str, add_path: str, dry_run: bool) -> None:
    with open(base_path, encoding="utf-8") as f:
        base: list[dict] = json.load(f)

    with open(add_path, encoding="utf-8") as f:
        additions: list[dict] = json.load(f)

    existing_urls = {page["url"] for page in base}
    new_pages = [p for p in additions if p["url"] not in existing_urls]
    duplicate_pages = [p for p in additions if p["url"] in existing_urls]

    print(f"Base dataset    : {len(base)} pages  ({base_path})")
    print(f"Pages to add    : {len(additions)} total, {len(new_pages)} new, {len(duplicate_pages)} duplicates skipped")

    if not new_pages:
        print("Nothing to merge — all URLs already present in base dataset.")
        return

    for p in new_pages:
        print(f"  + {p['url']}")

    if dry_run:
        print("\nDry run — no changes written.")
        return

    merged = base + new_pages
    with open(base_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    print(f"\nMerged. {base_path} now contains {len(merged)} pages.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge new pages into the base dataset JSON, deduplicating by URL."
    )
    parser.add_argument(
        "--add",
        required=True,
        metavar="FILE",
        help="JSON file with new pages to add (e.g. data/pages_calendar.json)",
    )
    parser.add_argument(
        "--base",
        default="data/pages_math.json",
        metavar="FILE",
        help="Base dataset to merge into (default: data/pages_math.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be merged without writing any changes.",
    )
    args = parser.parse_args()
    merge(args.base, args.add, args.dry_run)


if __name__ == "__main__":
    main()
