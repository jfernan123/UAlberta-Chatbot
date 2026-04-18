# js_scraper.py
"""
JavaScript-enabled scraper using Playwright
Extracts dynamic content from pages that require JavaScript rendering

Note: Some pages are server-side rendered so we use requests first,
then optionally use Playwright if JS rendering is needed.
"""

import json
import time
import random
import requests
from bs4 import BeautifulSoup

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


def fetch_with_requests(url, session=None):
    """
    Fetch HTML using requests (bypasses CloudFront blocking)
    
    Args:
        url: URL to scrape
        session: Optional requests.Session
    
    Returns:
        HTML content as string
    """
    if session is None:
        session = requests.Session()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.ualberta.ca/",
    }
    
    response = session.get(url, headers=headers)
    response.raise_for_status()
    
    return response.text, session


def fetch_with_playwright(url, wait_time=2):
    """
    Use Playwright to fetch page with JavaScript rendered
    (Used as fallback when requests don't work)
    
    Args:
        url: URL to scrape
        wait_time: Seconds to wait after page load (default 2)
    
    Returns:
        HTML content as string
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise RuntimeError("Playwright not available")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="/usr/bin/chromium",
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = browser.new_page()
        
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.ualberta.ca/",
        })
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
        except Exception:
            page.goto(url, timeout=30000)
        
        time.sleep(wait_time)
        
        html = page.content()
        browser.close()
        
    return html


def scrape_with_playwright(url, wait_time=3):
    """
    Use Playwright to fetch page with JavaScript rendered
    
    Args:
        url: URL to scrape
        wait_time: Seconds to wait after page load (default 3)
    
    Returns:
        HTML content as string
    """
    with sync_playwright() as p:
        # Launch browser in headless mode using system Chromium
        browser = p.chromium.launch(
            executable_path="/usr/bin/chromium",
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        page = browser.new_page()
        
        # Set custom headers to avoid CloudFront blocking
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.ualberta.ca/",
        })
        
        # Navigate to page and wait for network idle
        try:
            page.goto(url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            # Try alternative wait strategy
            page.goto(url, timeout=30000)
            page.wait_for_load_state("domcontentloaded")
        
        # Wait for dynamic content to load
        time.sleep(wait_time)
        
        # Get the fully rendered HTML
        html = page.content()
        browser.close()
        
    return html


def parse_html_to_sections(html, url):
    """
    Parse HTML to extract structured sections (same logic as scraper.py)
    
    Args:
        html: HTML content string
        url: URL of the page
    
    Returns:
        dict with url, title, sections
    """
    soup = BeautifulSoup(html, "html.parser")
    
    # Remove scripts/styles
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    
    # Get title
    title = soup.find("title").get_text(strip=True) if soup.find("title") else url
    
    # Extract structured sections (headings + following content)
    sections = []
    
    # Find all headings
    headings = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
    
    if headings:
        # Extract content BEFORE first heading (intro paragraphs)
        first_heading = headings[0]
        intro_content = []
        for sibling in first_heading.previous_siblings:
            if hasattr(sibling, "name") and sibling.name in ["p", "div"]:
                text = sibling.get_text(strip=True)
                if text and len(text) > 20:
                    intro_content.append(text)
        
        # Add intro as first section if found
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
            
            # Get following content until next heading
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
    
    return {"url": url, "title": title, "sections": sections}


def scrape_js_page(url, use_playwright=False):
    """
    Main function: Scrape a page with hybrid approach
    
    Args:
        url: URL to scrape
        use_playwright: If True, force using Playwright (for JS-heavy pages)
    
    Returns:
        dict with url, title, sections
    """
    print(f"Scraping (JS): {url}")
    
    html = None
    session = None
    
    try:
        time.sleep(random.uniform(1, 2))
        
        if use_playwright and PLAYWRIGHT_AVAILABLE:
            try:
                html = fetch_with_playwright(url)
            except Exception as e:
                print(f"  Playwright failed ({e}), trying requests...")
                html, session = fetch_with_requests(url)
        else:
            # Try requests first (faster and bypasses CloudFront)
            html, session = fetch_with_requests(url)
        
        # Parse to sections
        result = parse_html_to_sections(html, url)
        
        print(f"  Success: {len(result.get('sections', []))} sections")
        return result
        
    except Exception as e:
        print(f"  Error: {e}")
        return {"url": url, "title": f"Error: {str(e)}", "sections": []}


# =============================================================================
# Main: Test with specific pages
# =============================================================================

if __name__ == "__main__":
    import os
    
    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    
    # URLs to test with Playwright
    js_urls = [
        # MDP - Modeling, Data and Predictions (graduate)
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/graduate-studies/programs",
        # Statistics program (for intro)
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/undergraduate-studies/programs/statistics.html",
        # MDP Program website
        "https://sites.ualberta.ca/~mdpprog/",
    ]
    
    results = []
    for url in js_urls:
        result = scrape_js_page(url)
        results.append(result)
    
    # Save combined results
    output_file = "data/pages_js.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\nScraped {len(results)} JS pages, saved to {output_file}")
    
    # Summary
    total_sections = sum(len(r.get("sections", [])) for r in results)
    print(f"Total sections: {total_sections}")