# scraper.py
import requests
from bs4 import BeautifulSoup

def scrape_page(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Remove scripts/styles
    for tag in soup(["script", "style"]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    return text

if __name__ == "__main__":
    urls = [
        "https://calendar.ualberta.ca/...",
        "https://www.ualberta.ca/mathematical-and-statistical-sciences/..."
    ]

    all_text = []
    for url in urls:
        all_text.append(scrape_page(url))

    with open("data/raw_text.txt", "w", encoding="utf-8") as f:
        f.write("\n\n".join(all_text))