# hybrid_scraper.py
"""
Hybrid scraper combining:
- requests + BeautifulSoup for main site pages
- Regex extraction for calendar pages with course requirements
"""

import json
import time
import random
import re
import requests
from bs4 import BeautifulSoup


# =============================================================================
# HTTP/Request Functions
# =============================================================================

def create_session():
    """Create requests session with headers"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Referer": "https://www.ualberta.ca/",
        "Upgrade-Insecure-Requests": "1",
    })
    return session


def fetch_page(url, session):
    """Fetch HTML page with rate limiting"""
    time.sleep(random.uniform(1, 3))
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return response.text


# =============================================================================
# Extraction Functions
# =============================================================================

def extract_standard_sections(soup, url):
    """Extract sections from regular pages (main site)"""
    # Remove scripts/styles
    for tag in soup(["script", "style"]):
        tag.decompose()

    title = soup.find("title").get_text(strip=True) if soup.find("title") else url
    sections = []

    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

    if headings:
        # Extract content before first heading
        first_heading = headings[0]
        intro_content = []
        for sibling in first_heading.previous_siblings:
            if hasattr(sibling, "name") and sibling.name in ["p", "div"]:
                text = sibling.get_text(strip=True)
                if text and len(text) > 20:
                    intro_content.append(text)

        if intro_content:
            intro_heading = title.split("|")[0].strip() if "|" in title else "Introduction"
            sections.append({
                "heading": intro_heading,
                "content": " ".join(reversed(intro_content))
            })

        # Extract content after each heading
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
                    "p", "li", "td", "th", "tr", "div", "a", "ul", "ol",
                ]:
                    text = sibling.get_text(strip=True)
                    if text and len(text) > 5:
                        content_parts.append(text)

            if content_parts:
                sections.append({
                    "heading": heading_text,
                    "content": " ".join(content_parts)
                })

    return title, sections


def extract_course_content(text):
    """Extract course codes from calendar page text using regex"""
    patterns = [
        r'(STAT\s*\d+[^\n]{0,60})',
        r'(MATH\s*\d+[^\n]{0,60})',
        r'(CMPUT\s*\d+[^\n]{0,60})',
    ]

    course_lines = []
    seen = set()

    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            clean = m.strip().replace('\n', ' ')[:80]
            if clean and clean not in seen and len(clean) > 5:
                course_lines.append(clean)
                seen.add(clean)

    return course_lines[:30]


def extract_calendar_sections(soup, url):
    """Extract sections from calendar pages"""
    # Remove scripts/styles
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    title = soup.find("title").get_text(strip=True) if soup.find("title") else url
    sections = []

    # Get standard headings
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])

    for heading in headings:
        heading_text = heading.get_text(strip=True)
        if not heading_text or heading_text in ["Bachelor of Science Statistics Subject Area"]:
            continue

        content_parts = []
        for sibling in heading.next_siblings:
            if hasattr(sibling, "name") and sibling.name and sibling.name.startswith("h"):
                break
            if hasattr(sibling, "name") and sibling.name in ["p", "div", "li"]:
                text = sibling.get_text(strip=True)
                if text and len(text) > 10:
                    content_parts.append(text)

        if content_parts:
            sections.append({
                "heading": heading_text,
                "content": " ".join(content_parts)
            })

    # Extract course requirements via regex
    page_text = soup.get_text()
    course_lines = extract_course_content(page_text)

    if course_lines:
        sections.append({
            "heading": "Course Requirements",
            "content": " | ".join(course_lines)
        })

    return title, sections


# =============================================================================
# Main Scraper
# =============================================================================

def scrape_page(url):
    """Scrape a single page using appropriate method"""
    session = create_session()
    html = fetch_page(url, session)
    soup = BeautifulSoup(html, "html.parser")

    # Choose extraction method based on URL
    if "calendar" in url:
        title, sections = extract_calendar_sections(soup, url)
    else:
        title, sections = extract_standard_sections(soup, url)

    return {"url": url, "title": title, "sections": sections}


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import os
    os.makedirs("data", exist_ok=True)

    # URLs to scrape - main site + calendar
    urls = [
        # Program pages
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/undergraduate-studies/programs/index.html",
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/undergraduate-studies/programs/statistics.html",
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/undergraduate-studies/programs/mathematics.html",
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/undergraduate-studies/programs/mathematics-and-finance.html",
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/undergraduate-studies/programs/mathematics-and-economics.html",

        # Course page
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/undergraduate-studies/courses/first-year-courses/index.html",

        # Graduate programs
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/graduate-studies/programs",

        # MDP Program website
        "https://sites.ualberta.ca/~mdpprog/",

        # Calendar - Statistics requirements
        "https://calendar.ualberta.ca/preview_program.php?catoid=56&poid=84315",
    ]

    results = []
    for url in urls:
        print(f"Scraping: {url}")
        try:
            result = scrape_page(url)
            results.append(result)
            print(f"  Success: {len(result['sections'])} sections")
        except Exception as e:
            print(f"  Error: {e}")

    # Save results
    with open("data/pages.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    total_sections = sum(len(r.get("sections", [])) for r in results)
    print(f"\nScraped {len(results)} page(s), saved to data/pages.json")
    print(f"Total sections: {total_sections}")