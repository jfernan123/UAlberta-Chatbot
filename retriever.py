# retriever.py
import json
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

PAGES_FILE = "data/pages.json"


def _load_docs() -> list[Document]:
    with open(PAGES_FILE, encoding="utf-8") as f:
        pages = json.load(f)
    pages = [p for p in pages if not p.get("url", "").endswith("&print")]
    docs = []
    for page in pages:
        url = page.get("url", "")
        for section in page.get("sections", []):
            text = f"[Source: {url}] {section['heading']}: {section['content']}"
            docs.append(Document(page_content=text))
    return docs


def load_retriever(k: int = 6):
    docs = _load_docs()

    # Vector retriever (semantic similarity)
    vector_db = Chroma(
        persist_directory="db",
        embedding_function=OllamaEmbeddings(model="nomic-embed-text"),
    )
    vector_retriever = vector_db.as_retriever(search_kwargs={"k": k})

    # BM25 retriever (exact keyword match)
    bm25_retriever = BM25Retriever.from_documents(docs, k=k)

    # Manual ensemble: deduplicated union of both result sets
    # BM25 results go first so exact course-code matches rank higher
    def retrieve(query: str) -> list[Document]:
        bm25_results = bm25_retriever.invoke(query)
        vector_results = vector_retriever.invoke(query)
        seen: set[str] = set()
        combined = []
        for doc in bm25_results + vector_results:
            key = doc.page_content[:100]
            if key not in seen:
                seen.add(key)
                combined.append(doc)
        return combined[:k]

    # Wrap as a simple object with .invoke() so callers don't need to change
    class HybridRetriever:
        def __init__(self):
            self.search_kwargs = {"k": k}

        def invoke(self, query: str) -> list[Document]:
            _k = self.search_kwargs.get("k", k)
            bm25_results = bm25_retriever.invoke(query)
            vector_results = vector_retriever.invoke(query)
            seen: set[str] = set()
            combined = []
            for doc in bm25_results + vector_results:
                key = doc.page_content[:100]
                if key not in seen:
                    seen.add(key)
                    combined.append(doc)
            return combined[:_k]

    return HybridRetriever()
