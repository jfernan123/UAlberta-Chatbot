# scraper.py
import json
import requests
from bs4 import BeautifulSoup


def scrape_page(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive",
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    # Remove scripts/styles
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Get title
    title = soup.find("title").get_text(strip=True) if soup.find("title") else url

    # Extract structured sections (headings + following content)
    sections = []
    for heading in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
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
            ]:
                text = sibling.get_text(strip=True)
                if text:
                    content_parts.append(text)

        if content_parts:
            sections.append(
                {"heading": heading_text, "content": " ".join(content_parts)}
            )

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
        
        # Course page (only first-year available)
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/undergraduate-studies/courses/first-year-courses/index.html",
        
        # Graduate programs (MDP - Modeling, Data and Predictions)
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/graduate-studies/programs",
    ]

    # Note: Calendar pages removed as they require enhanced scraping for tables
    # To re-enable calendar scraping, enhance scraper to handle HTML tables
    # "https://calendar.ualberta.ca/preview_program.php?catoid=56&poid=84315",

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
