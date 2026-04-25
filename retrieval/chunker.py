import json
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def _source_type(url: str) -> str:
    if "calendar.ualberta.ca" in url:
        return "calendar"
    if "/graduate-studies/" in url:
        return "graduate"
    if "/undergraduate-studies/" in url:
        return "undergraduate"
    return "department"


def chunk_text(text: str) -> list[str]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=150)
    return splitter.split_text(text)


def chunk_json(json_file_path: str) -> list[Document]:
    with open(json_file_path, "r", encoding="utf-8") as f:
        pages = json.load(f)

    pages = [p for p in pages if not p.get("url", "").endswith("&print")]

    splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=150)
    documents = []

    for page in pages:
        url = page.get("url", "")
        source_type = _source_type(url)
        for section in page.get("sections", []):
            heading = section.get("heading", "")
            content = section.get("content", "")
            text = f"[Source: {url}] {heading}: {content}"
            for chunk in splitter.split_text(text):
                documents.append(Document(
                    page_content=chunk,
                    metadata={
                        "url": url,
                        "heading": heading,
                        "source_type": source_type,
                    },
                ))

    return documents
