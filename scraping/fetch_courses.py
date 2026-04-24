"""
fetch_courses.py

Fetches all STAT and MATH individual course pages from the UAlberta calendar
by querying the advanced search endpoint, then downloading each course page.
Saves HTML files into raw_html_calendar/ and updates its manifest.json.

The BFS crawler can't find these pages because the course listing is rendered
via paginated POST requests, not plain <a href> links.

Usage:
    python fetch_courses.py
    python fetch_courses.py --subjects STAT MATH CMPUT
"""

import argparse
import hashlib
import json
import os
import random
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

DEFAULT_SUBJECTS = ["STAT", "MATH"]
DEFAULT_OUT_DIR = "raw_html_calendar"
SEARCH_URL = "https://calendar.ualberta.ca/search_advanced.php?catoid=56"
BASE_URL = "https://calendar.ualberta.ca/"
REQUEST_DELAY = (1.0, 2.0)

session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://calendar.ualberta.ca/",
})


def url_to_filename(url: str) -> str:
    path = re.sub(r"[^a-zA-Z0-9._-]", "_", url.split("calendar.ualberta.ca/")[-1])
    short_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{path}__{short_hash}.html"


def get_course_links(subject: str) -> list[tuple[str, str]]:
    """Return list of (title, absolute_url) for all courses in a subject."""
    links = []
    page = 1
    while True:
        data = {
            "cur_cat_oid": "56",
            "search_database": "Search",
            "search_db": "Courses",
            "cpage": str(page),
            "filter[27]": subject,
            "filter[item_type]": "3",
            "filter[only_active]": "1",
            "filter[3]": "1",
        }
        r = session.post(SEARCH_URL, data=data, timeout=30)
        soup = BeautifulSoup(r.text, "html.parser")
        page_links = [
            (a.get_text(strip=True), urljoin(BASE_URL, a["href"]))
            for a in soup.find_all("a", href=True)
            if "preview_course_nopop" in a["href"]
        ]
        if not page_links:
            break
        links.extend(page_links)
        # Check if there's a next page
        next_pg = soup.find("a", string=str(page + 1))
        if not next_pg:
            break
        page += 1
        time.sleep(random.uniform(*REQUEST_DELAY))

    return links


def fetch_and_save(url: str, out_dir: Path) -> str | None:
    """Download a course page, save to out_dir, return filename."""
    time.sleep(random.uniform(*REQUEST_DELAY))
    try:
        r = session.get(url, timeout=30, allow_redirects=True)
        r.raise_for_status()
    except requests.RequestException as exc:
        print(f"    SKIP  {url}  ({exc})")
        return None
    filename = url_to_filename(url)
    with open(out_dir / filename, "w", encoding="utf-8") as f:
        f.write(r.text)
    return filename


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch STAT/MATH course pages from UAlberta calendar."
    )
    parser.add_argument(
        "--subjects", nargs="+", default=DEFAULT_SUBJECTS,
        help=f"Course subject codes to fetch (default: {DEFAULT_SUBJECTS})"
    )
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(exist_ok=True)
    manifest_path = out_dir / "manifest.json"

    # Load existing manifest to skip already-downloaded URLs
    manifest: list[dict] = []
    already_have: set[str] = set()
    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        already_have = {e["url"] for e in manifest}
        print(f"Existing manifest: {len(manifest)} pages, skipping already downloaded.")

    for subject in args.subjects:
        print(f"\nFetching {subject} course list...")
        course_links = get_course_links(subject)
        print(f"  Found {len(course_links)} {subject} courses.")

        new = [(title, url) for title, url in course_links if url not in already_have]
        print(f"  {len(new)} new (not yet downloaded).")

        for i, (title, url) in enumerate(new, start=1):
            print(f"  [{i:>3}/{len(new)}]  {title}")
            filename = fetch_and_save(url, out_dir)
            if filename:
                manifest.append({"url": url, "file": filename})
                already_have.add(url)
                # Save manifest after every page
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\nDone. Manifest now has {len(manifest)} pages.")
    print(f"Run: python calendar_parser.py && python make_db.py -v")


if __name__ == "__main__":
    main()
