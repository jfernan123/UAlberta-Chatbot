# scraper.py
import json
import time
import random
import requests
from bs4 import BeautifulSoup


# Create a session for better request handling
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


def scrape_page(url):
    # Add random delay between requests (1-3 seconds)
    time.sleep(random.uniform(1, 3))
    
    response = session.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # Remove scripts/styles
    for tag in soup(["script", "style"]):
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
                if text and len(text) > 20:  # Filter out short junk
                    intro_content.append(text)
        
        # Add intro as first section if found
        if intro_content:
            # Get page title from URL or use first intro line as heading
            intro_heading = title.split("|")[0].strip() if "|" in title else "Introduction"
            sections.append({
                "heading": intro_heading,
                "content": " ".join(reversed(intro_content))  # Reverse to get correct order
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
                    "p",
                    "li",
                    "td",
                    "th",
                    "tr",
                    "div",
                    "a",  # Add anchor links for degree options
                    "ul",
                    "ol",
                ]:
                    text = sibling.get_text(strip=True)
                    if text and len(text) > 5:  # Filter very short text
                        content_parts.append(text)

            if content_parts:
                sections.append(
                    {"heading": heading_text, "content": " ".join(content_parts)}
                )
    
    # For calendar pages, also extract all tables separately
    if "calendar" in url:
        table_sections = extract_all_tables(soup)
        sections.extend(table_sections)

    return {"url": url, "title": title, "sections": sections}


if __name__ == "__main__":
    import os

    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)

    urls = [
        # Program pages (fixed URLs - these now work)
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/undergraduate-studies/programs/index.html",
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/undergraduate-studies/programs/statistics.html",
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/undergraduate-studies/programs/mathematics.html",
        
        # Additional program pages
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/undergraduate-studies/programs/mathematics-and-finance.html",
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/undergraduate-studies/programs/mathematics-and-economics.html",
        
        # Course page (only first-year available)
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/undergraduate-studies/courses/first-year-courses/index.html",
        
        # Graduate programs (MDP - Modeling, Data and Predictions)
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/graduate-studies/programs",
        
        # MDP Program website (separate site with full program details)
        "https://sites.ualberta.ca/~mdpprog/",
        
        # Calendar pages - requires JavaScript rendering (currently commented out)
        # "https://calendar.ualberta.ca/preview_program.php?catoid=56&poid=84315",  # Statistics
        # "https://calendar.ualberta.ca/preview_program.php?catoid=56&poid=84314",  # Mathematics
    ]

    results = []
    for url in urls:
        print(f"Scraping: {url}")
        try:
            results.append(scrape_page(url))
            print(f"  Success")
        except Exception as e:
            print(f"  Error: {e}")

    with open("data/pages.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\nScraped {len(results)} page(s), saved to data/pages.json")

    # Count total sections
    total_sections = sum(len(page.get("sections", [])) for page in results)
    print(f"Total sections: {total_sections}")
