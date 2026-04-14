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
        # Calendar pages
        # "https://calendar.ualberta.ca/",
        # Program pages
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/undergraduate-studies/programs/index.html",
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/undergraduate-studies/courses/first-year-courses/index.html",
    ]

    results = []
    for url in urls:
        results.append(scrape_page(url))

    with open("data/pages.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Scraped {len(results)} page(s), saved to data/pages.json")
