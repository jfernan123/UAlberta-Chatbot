# parsers.py
"""
Shared BeautifulSoup parsing logic for HTML content extraction.
Used by both direct URL scrapers and HTML file processing.
"""

import re
import time
import random
import requests
from bs4 import BeautifulSoup


def create_session():
    """Create requests session with headers"""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Referer": "https://www.ualberta.ca/",
            "Upgrade-Insecure-Requests": "1",
        }
    )
    return session


def fetch_page(url, session=None):
    """Fetch HTML page with rate limiting"""
    if session is None:
        session = create_session()

    time.sleep(random.uniform(1, 3))
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.text


def extract_course_content(text):
    """Extract course codes from text using regex"""
    patterns = [
        r"(STAT\s*\d+[^\n]{0,60})",
        r"(MATH\s*\d+[^\n]{0,60})",
        r"(CMPUT\s*\d+[^\n]{0,60})",
    ]

    course_lines = []
    seen = set()

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            clean = m.strip().replace("\n", " ")[:80]
            if clean and clean not in seen and len(clean) > 5:
                course_lines.append(clean)
                seen.add(clean)

    return course_lines[:30]


def parse_html_to_sections(html, url):
    """
    Parse HTML to extract structured sections.

    Args:
        html: HTML content as string
        url: URL of the page (used for title fallback)

    Returns:
        dict with keys: url, title, sections (list of {heading, content})
    """
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    title = soup.find("title").get_text(strip=True) if soup.find("title") else url

    sections = []
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

    if headings:
        first_heading = headings[0]
        intro_content = []
        for sibling in first_heading.previous_siblings:
            if hasattr(sibling, "name") and sibling.name in ["p", "div"]:
                text = sibling.get_text(strip=True)
                if text and len(text) > 20:
                    intro_content.append(text)

        if intro_content:
            intro_heading = (
                title.split("|")[0].strip() if "|" in title else "Introduction"
            )
            sections.append(
                {"heading": intro_heading, "content": " ".join(reversed(intro_content))}
            )

        for heading in headings:
            heading_text = heading.get_text(strip=True)
            if not heading_text:
                continue

            content_parts = []
            for sibling in heading.next_siblings:
                if (
                    hasattr(sibling, "name")
                    and sibling.name
                    and sibling.name.startswith("h")
                ):
                    break
                if hasattr(sibling, "name") and sibling.name in [
                    "p",
                    "li",
                    "td",
                    "th",
                    "tr",
                    "div",
                    "a",
                    "ul",
                    "ol",
                ]:
                    text = sibling.get_text(strip=True)
                    if text and len(text) > 5:
                        content_parts.append(text)

            if content_parts:
                sections.append(
                    {"heading": heading_text, "content": " ".join(content_parts)}
                )

    if "calendar" in url:
        page_text = soup.get_text()
        course_lines = extract_course_content(page_text)
        if course_lines:
            sections.append(
                {"heading": "Course Requirements", "content": " | ".join(course_lines)}
            )

    return {"url": url, "title": title, "sections": sections}


def parse_html_file(filepath, url=None):
    """
    Parse a single HTML file.

    Args:
        filepath: Path to HTML file
        url: Optional URL override (otherwise derived from filename)

    Returns:
        dict with keys: url, title, sections
    """
    with open(filepath, "r", encoding="utf-8") as f:
        html = f.read()

    return parse_html_to_sections(html, url if url else filepath)
