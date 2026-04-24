"""
web_crawler.py

Crawls a university department website and saves raw HTML to disk.

Stopping conditions (in priority order):
  1. URL prefix  — only follows links that stay within a configured URL prefix.
                   This is the primary bound: it keeps the crawl scoped to the
                   target department and stops naturally when no new in-scope
                   links are found.
  2. Visited set — never revisits a URL (deduplication).
  3. Max pages   — hard safety cap so a misconfigured prefix can't run forever.

Re-running is safe: already-downloaded pages in manifest.json are skipped.

Usage:
    # Math & Stats department pages (default)
    python web_crawler.py

    # Academic calendar — course listings and requirements
    python web_crawler.py \\
        --start-url "https://calendar.ualberta.ca/content.php?catoid=56&navoid=13680" \\
        --prefix    "https://calendar.ualberta.ca/" \\
        --out-dir   raw_html_calendar

    # Custom run
    python web_crawler.py --start-url <url> --prefix <prefix> --max-pages 500 --out-dir raw_html
"""

import argparse
import hashlib
import json
import os
import random
import re
import time
from collections import deque
from urllib.parse import urljoin, urlparse, urldefrag

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

DEFAULT_START_URL = (
    "https://www.ualberta.ca/en/mathematical-and-statistical-sciences/index.html"
)
DEFAULT_PREFIX = "https://www.ualberta.ca/en/mathematical-and-statistical-sciences/"
DEFAULT_OUT_DIR = "raw_html"
DEFAULT_MAX_PAGES = 1000
REQUEST_DELAY = (1.0, 3.0)  # seconds, uniform random


# ---------------------------------------------------------------------------
# HTTP session
# ---------------------------------------------------------------------------

session = requests.Session()
session.headers.update(
    {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Referer": "https://www.ualberta.ca/",
        "Upgrade-Insecure-Requests": "1",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_url(url: str) -> str:
    """Strip fragment, normalize trailing slash, and lower-case scheme+host."""
    url, _ = urldefrag(url)          # remove #fragment
    parsed = urlparse(url)
    # lower-case scheme and host; keep path as-is (UAlberta paths are case-sensitive)
    normalized = parsed._replace(scheme=parsed.scheme.lower(), netloc=parsed.netloc.lower())
    return normalized.geturl().rstrip("/")


def url_to_filename(url: str) -> str:
    """Turn a URL into a safe filename: sanitized path + short hash suffix."""
    parsed = urlparse(url)
    path = parsed.path.strip("/").replace("/", "__")
    path = re.sub(r"[^a-zA-Z0-9._-]", "_", path) or "index"
    # Append a short hash to avoid collisions on long/similar paths
    short_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{path}__{short_hash}.html"


def is_html_url(url: str) -> bool:
    """Return True if the URL looks like an HTML page (not a binary asset)."""
    skip_extensions = {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".zip", ".tar", ".gz", ".rar",
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico",
        ".mp3", ".mp4", ".avi", ".mov",
        ".css", ".js", ".json", ".xml",
    }
    path = urlparse(url).path.lower()
    _, ext = os.path.splitext(path)
    return ext not in skip_extensions


def extract_links(html: str, base_url: str) -> list[str]:
    """Return all absolute URLs found in <a href=...> tags."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or href.startswith("mailto:") or href.startswith("tel:") or href.startswith("javascript:"):
            continue
        absolute = urljoin(base_url, href)
        links.append(absolute)
    return links


# ---------------------------------------------------------------------------
# Crawler
# ---------------------------------------------------------------------------

def crawl(
    start_url: str,
    prefix: str,
    out_dir: str,
    max_pages: int,
) -> None:
    os.makedirs(out_dir, exist_ok=True)
    manifest_path = os.path.join(out_dir, "manifest.json")

    visited: set[str] = set()
    queue: deque[str] = deque()
    manifest: list[dict] = []

    # Resume: load existing manifest so already-downloaded pages are skipped
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
        for entry in manifest:
            visited.add(normalize_url(entry["url"]))
        print(f"Resuming — {len(visited)} pages already downloaded, skipping them.")

    start_url = normalize_url(start_url)
    queue.append(start_url)

    print(f"Starting crawl from : {start_url}")
    print(f"URL prefix filter   : {prefix}")
    print(f"Max pages           : {max_pages}")
    print(f"Output directory    : {out_dir}")
    print("-" * 60)

    while queue and len(visited) < max_pages:
        url = queue.popleft()
        url = normalize_url(url)

        if url in visited:
            continue

        # --- Primary stopping condition: URL prefix ---
        if not url.startswith(prefix):
            continue

        if not is_html_url(url):
            continue

        visited.add(url)

        # Polite delay
        time.sleep(random.uniform(*REQUEST_DELAY))

        try:
            response = session.get(url, timeout=30, allow_redirects=True)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"  SKIP  {url}  ({exc})")
            continue

        # Respect redirects: if the final URL left the prefix, discard
        final_url = normalize_url(response.url)
        if not final_url.startswith(prefix):
            print(f"  REDIR {url} -> {final_url}  (out of prefix, skipping)")
            continue

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type:
            print(f"  SKIP  {url}  (content-type: {content_type})")
            continue

        html = response.text
        filename = url_to_filename(final_url)
        filepath = os.path.join(out_dir, filename)

        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(html)

        page_count = len(visited)
        print(f"  [{page_count:>4}]  {final_url}")

        manifest.append({"url": final_url, "file": filename})

        # Save manifest after every page so a crash doesn't lose progress
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh, indent=2, ensure_ascii=False)

        # Discover new links
        new_links = extract_links(html, final_url)
        for link in new_links:
            norm = normalize_url(link)
            if norm not in visited and norm.startswith(prefix):
                queue.append(norm)

    print("-" * 60)
    print(f"Crawl complete. Pages saved: {len(manifest)}")
    print(f"Manifest written to: {manifest_path}")

    if len(visited) >= max_pages:
        print(f"NOTE: Stopped because max_pages ({max_pages}) was reached.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crawl a UAlberta department website and save raw HTML."
    )
    parser.add_argument(
        "--start-url",
        default=DEFAULT_START_URL,
        help=f"Seed URL to begin crawling (default: {DEFAULT_START_URL})",
    )
    parser.add_argument(
        "--prefix",
        default=DEFAULT_PREFIX,
        help=(
            "Only follow URLs that start with this prefix. "
            f"(default: {DEFAULT_PREFIX})"
        ),
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUT_DIR,
        help=f"Directory to save HTML files (default: {DEFAULT_OUT_DIR})",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help=f"Hard cap on number of pages to download (default: {DEFAULT_MAX_PAGES})",
    )
    args = parser.parse_args()

    crawl(
        start_url=args.start_url,
        prefix=args.prefix,
        out_dir=args.out_dir,
        max_pages=args.max_pages,
    )


if __name__ == "__main__":
    main()
