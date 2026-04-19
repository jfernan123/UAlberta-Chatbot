"""
html_parser.py

Uses Claude to extract clean, structured content from raw HTML files.
Reads from raw_html/ (produced by web_crawler.py) and writes to data/pages.json.

Runs requests concurrently (default 10 at a time) using asyncio + AsyncAnthropic.
The system prompt is prompt-cached so you only pay full price on the first call.

Usage:
    python html_parser.py
    python html_parser.py --manifest raw_html/manifest.json --out data/pages.json
    python html_parser.py --concurrency 20   # push harder (watch rate limits)
    python html_parser.py --limit 10         # test on first 10 pages
    python html_parser.py --resume           # skip already-parsed URLs
"""

import argparse
import asyncio
import json
import os
from pathlib import Path

import anthropic
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_MANIFEST = "raw_html/manifest.json"
DEFAULT_OUT = "data/pages.json"
DEFAULT_MODEL = "claude-haiku-4-5"
DEFAULT_CONCURRENCY = 5
MAX_HTML_CHARS = 60_000

# ---------------------------------------------------------------------------
# System prompt — cached after the first call in each 5-minute window
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You extract structured content from University of Alberta math/stats department web pages.

Given raw HTML, return ONLY a JSON object with this exact structure:
{
  "title": "page title as a string",
  "sections": [
    {
      "heading": "section heading",
      "content": "section body text as clean prose"
    }
  ],
  "links": [
    {
      "text": "link anchor text",
      "url": "absolute or relative URL"
    }
  ]
}

Rules for sections:
- Extract ONLY meaningful content: program descriptions, course info, faculty profiles,
  academic policies, admission requirements, research areas, events, news.
- IGNORE: navigation menus, footers, breadcrumbs, sidebars, cookie banners,
  login prompts, social media links, search bars, repeated site-wide notices.
- Split content at headings (h1–h4). If there are no clear headings, return a single
  section using the page title as the heading.
- Keep ALL factual details (deadlines, prerequisites, contact info, GPA thresholds, etc.).
- Output clean prose — no HTML tags, no markdown, no bullet characters in content.
- If the page has no meaningful content (e.g. pure navigation page), return sections: [].

Rules for links:
- Include links that a student or researcher would find useful: course pages, program
  pages, faculty profiles, admission pages, academic calendar entries, contact pages,
  research group pages, related department pages.
- EXCLUDE: navigation menu links, footer links, social media, login/logout, search,
  cookie/privacy policy pages, generic "home" or "back" links, duplicate links.
- Use the link text as written in the HTML (clean, no surrounding whitespace).
- If no useful links are found, return links: [].
"""

# JSON schema for structured output
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["heading", "content"],
                "additionalProperties": False,
            },
        },
        "links": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["text", "url"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "sections", "links"],
    "additionalProperties": False,
}


# ---------------------------------------------------------------------------
# HTML pre-processing
# ---------------------------------------------------------------------------

def preprocess_html(html: str) -> str:
    """Strip scripts/styles/media, return cleaned HTML body, truncated."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe",
                     "svg", "img", "video", "audio", "picture"]):
        tag.decompose()
    body = soup.find("body") or soup
    cleaned = str(body)
    if len(cleaned) > MAX_HTML_CHARS:
        cleaned = cleaned[:MAX_HTML_CHARS] + "\n<!-- [truncated] -->"
    return cleaned


# ---------------------------------------------------------------------------
# Async Claude call
# ---------------------------------------------------------------------------

async def parse_page(
    client: anthropic.AsyncAnthropic,
    html: str,
    url: str,
    model: str,
) -> dict:
    """Send cleaned HTML to Claude and return a structured page dict."""
    cleaned = preprocess_html(html)

    async with client.messages.stream(
        model=model,
        max_tokens=8192,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": OUTPUT_SCHEMA,
            }
        },
        messages=[
            {
                "role": "user",
                "content": f"URL: {url}\n\nHTML:\n{cleaned}",
            }
        ],
    ) as stream:
        final = await stream.get_final_message()

    text_block = next((b for b in final.content if b.type == "text"), None)
    if text_block is None:
        raise ValueError("No text block in Claude response")

    parsed = json.loads(text_block.text)
    return {
        "url": url,
        "title": parsed["title"],
        "sections": parsed["sections"],
        "links": parsed.get("links", []),
    }


# ---------------------------------------------------------------------------
# Worker — semaphore-limited, writes result to shared list under a lock
# ---------------------------------------------------------------------------

async def process_entry(
    entry: dict,
    index: int,
    total: int,
    html_dir: Path,
    client: anthropic.AsyncAnthropic,
    model: str,
    semaphore: asyncio.Semaphore,
    results: list,
    errors: list,
    out_path: Path,
    write_lock: asyncio.Lock,
) -> None:
    url = entry["url"]
    html_file = html_dir / entry["file"]

    if not html_file.exists():
        print(f"  [{index:>4}/{total}]  MISSING  {html_file.name}")
        errors.append(url)
        return

    with open(html_file, encoding="utf-8", errors="replace") as f:
        html = f.read()

    async with semaphore:
        page = None
        for attempt in range(5):
            try:
                page = await parse_page(client, html, url, model)
                break
            except Exception as exc:
                is_rate_limit = (
                    isinstance(exc, anthropic.RateLimitError)
                    or (hasattr(exc, "status_code") and exc.status_code == 429)
                    or "429" in str(exc)
                    or "rate_limit" in str(exc)
                )
                if is_rate_limit:
                    wait = 60 * (attempt + 1)  # 60s, 120s, 180s ...
                    print(f"  [{index:>4}/{total}]  RATE LIMIT — waiting {wait}s  {url}")
                    await asyncio.sleep(wait)
                else:
                    print(f"  [{index:>4}/{total}]  ERROR  {url}  — {exc}")
                    errors.append(url)
                    return
        if page is None:
            print(f"  [{index:>4}/{total}]  FAILED after retries  {url}")
            errors.append(url)
            return

    print(f"  [{index:>4}/{total}]  OK ({len(page['sections'])} sections)  {url}")

    # Append result and persist under lock so concurrent writes don't corrupt the file
    async with write_lock:
        results.append(page)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest)
    html_dir = Path(args.html_dir) if args.html_dir else manifest_path.parent

    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        print("Run web_crawler.py first.")
        return

    with open(manifest_path, encoding="utf-8") as f:
        manifest: list[dict] = json.load(f)

    if args.limit:
        manifest = manifest[: args.limit]

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
    print(f"Model          : {args.model}")
    print(f"Concurrency    : {args.concurrency}")
    print(f"Output         : {out_path}")
    print("-" * 60)

    if not todo:
        print("Nothing to do.")
        return

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY environment variable not set.")
        return

    client = anthropic.AsyncAnthropic(api_key=api_key)
    semaphore = asyncio.Semaphore(args.concurrency)
    write_lock = asyncio.Lock()
    results: list[dict] = list(existing)
    errors: list[str] = []

    async def launch_staggered():
        tasks = []
        for i, entry in enumerate(todo, start=1):
            task = asyncio.create_task(process_entry(
                entry=entry,
                index=i,
                total=len(todo),
                html_dir=html_dir,
                client=client,
                model=args.model,
                semaphore=semaphore,
                results=results,
                errors=errors,
                out_path=out_path,
                write_lock=write_lock,
            ))
            tasks.append(task)
            await asyncio.sleep(1.0)  # 1s between launches to avoid token spike
        await asyncio.gather(*tasks)

    await launch_staggered()

    print("-" * 60)
    print(f"Done. Parsed: {len(results) - len(existing)}  |  Errors: {len(errors)}")
    print(f"Output written to: {out_path}")

    if errors:
        print(f"\nFailed URLs ({len(errors)}):")
        for url in errors:
            print(f"  {url}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse crawled HTML files using Claude (concurrent)."
    )
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--html-dir", default=None)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Max simultaneous API requests (default: {DEFAULT_CONCURRENCY})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process the first N pages (useful for testing).",
    )
    parser.add_argument(
        "--new",
        action="store_true",
        help="Wipe the output file and start fresh (default is to merge).",
    )
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
