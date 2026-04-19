# chunker.py
import json
from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_text(text):
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
    return splitter.split_text(text)


def chunk_json(json_file_path):
    with open(json_file_path, "r", encoding="utf-8") as f:
        pages = json.load(f)

    # Deduplicate print versions of pages (e.g. ?...&print)
    pages = [p for p in pages if not p.get("url", "").endswith("&print")]

    texts = []
    for page in pages:
        url = page.get("url", "")
        for section in page.get("sections", []):
            # Combine heading + content, include source URL
            text = f"[Source: {url}] {section['heading']}: {section['content']}"
            texts.append(text)

    splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)

    chunks = []
    for text in texts:
        chunks.extend(splitter.split_text(text))

    return chunks
