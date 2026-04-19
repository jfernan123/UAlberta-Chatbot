"""
calendar_parser.py

Classical (no-LLM) parser for UAlberta Acalog calendar pages.
Reads from raw_html_calendar/ (produced by web_crawler.py) and appends to data/pages.json.

Three page types handled automatically:
  - preview_course_nopop.php  — course detail pages (key-value fields + description)
  - preview_program.php       — program/subject-area pages (requirement sections)
  - content.php               — general calendar content pages (headings + paragraphs)

Output format matches html_parser.py: {url, title, sections[], links[]}

Usage:
    python calendar_parser.py
    python calendar_parser.py --manifest raw_html_calendar/manifest.json
    python calendar_parser.py --out data/pages.json --resume
"""

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_MANIFEST = "raw_html_calendar/manifest.json"
DEFAULT_OUT = "data/pages.json"

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def get_main(soup: BeautifulSoup):
    """Return the main content block for all Acalog page types."""
    return soup.find("td", class_="block_content")


def clean_text(text: str) -> str:
    """Collapse whitespace and strip zero-width characters."""
    text = re.sub(r"[\u200b\u00ad\xa0]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def extract_useful_links(main, base_url: str) -> list[dict]:
    """
    Return links that are useful to a student — course pages, program pages,
    calendar content pages. Exclude nav/print/help/social/back-to-top links.
    """
    SKIP_PATTERNS = re.compile(
        r"(javascript:|mailto:|print|help\.php|back.to.top|"
        r"social|login|logout|search|cookie|privacy|#$)",
        re.IGNORECASE,
    )
    USEFUL_PATHS = re.compile(
        r"(preview_course|preview_program|content\.php|"
        r"preview_entity|index\.php)",
        re.IGNORECASE,
    )

    seen: set[str] = set()
    links = []
    for tag in main.find_all("a", href=True):
        href = tag["href"].strip()
        if not href or SKIP_PATTERNS.search(href):
            continue
        text = clean_text(tag.get_text())
        if not text or len(text) < 3:
            continue
        absolute = urljoin(base_url, href)
        # Keep only calendar-internal useful links
        if not USEFUL_PATHS.search(href) and "calendar.ualberta.ca" not in absolute:
            continue
        if absolute in seen:
            continue
        seen.add(absolute)
        links.append({"text": text, "url": absolute})
    return links


# ---------------------------------------------------------------------------
# Page-type parsers
# ---------------------------------------------------------------------------

def parse_course_page(main, url: str) -> dict:
    """
    Handles preview_course_nopop.php pages.

    Structure: <h1 id="course_preview_title">COURSE_CODE - Name</h1>
    followed by <strong>Field</strong> Value pairs, then a Description block.
    """
    # Title
    h1 = main.find("h1", id="course_preview_title")
    title = clean_text(h1.get_text()) if h1 else "Unknown Course"

    # The course metadata lives in a flat <p> with alternating <strong> / text nodes
    p = main.find("p")
    fields = {}
    description = ""

    if p:
        # Walk children: <strong> tags give field names, NavigableString gives values
        current_key = None
        for child in p.children:
            if hasattr(child, "name") and child.name == "strong":
                current_key = clean_text(child.get_text())
            elif current_key:
                fragment = clean_text(str(child) if hasattr(child, "name") else child)
                # Strip residual HTML tags from description fragments
                fragment = re.sub(r"<[^>]+>", "", fragment).strip()
                if fragment:
                    fields[current_key] = fields.get(current_key, "") + " " + fragment
                    fields[current_key] = fields[current_key].strip()

    description = fields.pop("Description", "")

    # Build a single section with metadata + description
    meta_lines = [f"{k}: {v}" for k, v in fields.items() if v]
    content_parts = meta_lines
    if description:
        content_parts.append(description)
    content = "  ".join(content_parts)

    sections = [{"heading": title, "content": content}] if content else []
    links = extract_useful_links(main, url)
    return {"url": url, "title": title, "sections": sections, "links": links}


def parse_program_page(main, url: str) -> dict:
    """
    Handles preview_program.php pages.

    Structure: <h1 id="acalog-content"> then a series of <div class="acalog-core">
    blocks, each containing an h2/h3 heading + content (paragraphs, course lists).
    """
    h1 = main.find("h1", id="acalog-content")
    title = clean_text(h1.get_text()) if h1 else "Unknown Program"

    sections = []
    # Each logical section lives in a div.acalog-core
    for core_div in main.find_all("div", class_="acalog-core"):
        heading_tag = core_div.find(["h1", "h2", "h3", "h4"])
        if not heading_tag:
            continue
        heading = clean_text(heading_tag.get_text())

        # Collect text from paragraphs and course list items
        parts = []
        for el in core_div.find_all(["p", "li"]):
            text = clean_text(el.get_text())
            if text and len(text) > 3:
                parts.append(text)

        content = "  ".join(parts)
        if heading or content:
            sections.append({"heading": heading, "content": content})

    # Fallback: if no acalog-core divs found, parse headings generically
    if not sections:
        sections = parse_generic_sections(main, title)

    links = extract_useful_links(main, url)
    return {"url": url, "title": title, "sections": sections, "links": links}


def parse_content_page(main, soup: BeautifulSoup, url: str) -> dict:
    """
    Handles content.php and other general calendar pages.

    Extracts the page title from <h1 id="acalog-content"> or <title>,
    then splits content at h1-h4 headings.
    """
    # Remove the Acalog header row (contains HELP / ARCHIVED CALENDAR boilerplate)
    # It's always the first <tr> inside the outer table.table_default
    outer_table = main.find("table", class_="table_default")
    if outer_table:
        first_tr = outer_table.find("tr")
        if first_tr:
            first_tr.decompose()

    h1 = main.find("h1", id="acalog-content")
    if h1:
        title = clean_text(h1.get_text())
    else:
        title_tag = soup.find("title")
        raw = title_tag.get_text() if title_tag else url
        # Strip " - University of Alberta" suffix
        title = clean_text(raw.split(" - University of Alberta")[0])

    sections = parse_generic_sections(main, title)
    links = extract_useful_links(main, url)
    return {"url": url, "title": title, "sections": sections, "links": links}


def parse_generic_sections(main, page_title: str) -> list[dict]:
    """
    Generic heading-based section extractor used for content pages and
    as a fallback for program pages.
    """
    NOISE = re.compile(
        r"(HELP\s*$|Back to Top|Print-Friendly|ARCHIVED CALENDAR|"
        r"University of Alberta Calendar 20\d\d|^\s*\[ARCHIVED|"
        r"Print this Page|opens a new window)",
        re.IGNORECASE,
    )

    sections = []
    current_heading = page_title
    current_parts: list[str] = []

    def flush():
        content = "  ".join(current_parts).strip()
        if content:
            sections.append({"heading": current_heading, "content": content})

    for el in main.find_all(["h1", "h2", "h3", "h4", "p", "li", "td"]):
        if el.name in ("h1", "h2", "h3", "h4"):
            text = clean_text(el.get_text())
            if NOISE.match(text) or not text:
                continue
            flush()
            current_heading = text
            current_parts = []
        else:
            text = clean_text(el.get_text())
            if not text or len(text) < 10 or NOISE.match(text):
                continue
            # Skip if this element is a child of a heading we already captured
            if el.find_parent(["h1", "h2", "h3", "h4"]):
                continue
            current_parts.append(text)

    flush()
    return sections


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def parse_page(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    main = get_main(soup)

    if main is None:
        # No Acalog content block — return empty
        title_tag = soup.find("title")
        title = clean_text(title_tag.get_text()) if title_tag else url
        return {"url": url, "title": title, "sections": [], "links": []}

    if "preview_course_nopop.php" in url:
        return parse_course_page(main, url)
    elif "preview_program.php" in url:
        return parse_program_page(main, url)
    else:
        return parse_content_page(main, soup, url)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main_fn(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest)
    html_dir = manifest_path.parent

    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        print("Run web_crawler.py first.")
        return

    with open(manifest_path, encoding="utf-8") as f:
        manifest: list[dict] = json.load(f)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    existing: list[dict] = []
    already_parsed: set[str] = set()
    if not args.new and out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            existing = json.load(f)
        already_parsed = {page["url"] for page in existing}
        print(f"Merging — {len(already_parsed)} pages already in output.")

    todo = [e for e in manifest if e["url"] not in already_parsed]

    print(f"Pages to parse : {len(todo)}")
    print(f"Output         : {out_path}")
    print("-" * 60)

    if not todo:
        print("Nothing to do.")
        return

    results: list[dict] = list(existing)
    errors: list[str] = []

    for i, entry in enumerate(todo, start=1):
        url = entry["url"]
        html_file = html_dir / entry["file"]

        if not html_file.exists():
            print(f"  [{i:>4}/{len(todo)}]  MISSING  {html_file.name}")
            errors.append(url)
            continue

        with open(html_file, encoding="utf-8", errors="replace") as f:
            html = f.read()

        try:
            page = parse_page(html, url)
            results.append(page)
            print(f"  [{i:>4}/{len(todo)}]  OK ({len(page['sections'])} sections)  {url}")
        except Exception as exc:
            print(f"  [{i:>4}/{len(todo)}]  ERROR  {url}  — {exc}")
            errors.append(url)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("-" * 60)
    print(f"Done. Parsed: {len(results) - len(existing)}  |  Errors: {len(errors)}")
    print(f"Output written to: {out_path}")

    if errors:
        print(f"\nFailed ({len(errors)}):")
        for url in errors:
            print(f"  {url}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse UAlberta Acalog calendar HTML files (no LLM required)."
    )
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument(
        "--new",
        action="store_true",
        help="Wipe the output file and start fresh (default is to merge).",
    )
    args = parser.parse_args()
    main_fn(args)


if __name__ == "__main__":
    main()
