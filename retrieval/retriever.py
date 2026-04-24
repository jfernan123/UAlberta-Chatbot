# retriever.py
import json
from langchain_chroma import Chroma
from .embeddings import get_embeddings
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

PAGES_FILES = [
    "data/pages_math.json",
    "data/pages_calendar.json",
    "data/pages_synthetic.json",
]


def _load_docs() -> list[Document]:
    docs = []
    for path in PAGES_FILES:
        with open(path, encoding="utf-8") as f:
            pages = json.load(f)
        pages = [p for p in pages if not p.get("url", "").endswith("&print")]
        for page in pages:
            url = page.get("url", "")
            for section in page.get("sections", []):
                text = f"[Source: {url}] {section['heading']}: {section['content']}"
                docs.append(Document(page_content=text))
    return docs


def _rrf_score(rank: int, rrf_k: int = 60) -> float:
    return 1.0 / (rrf_k + rank)


def load_retriever(k: int = 10):
    docs = _load_docs()

    # Vector retriever (semantic similarity)
    vector_db = Chroma(
        persist_directory="db",
        embedding_function=get_embeddings(),
    )
    vector_retriever = vector_db.as_retriever(search_kwargs={"k": k})

    # BM25 retriever (exact keyword match)
    bm25_retriever = BM25Retriever.from_documents(docs, k=k)

    class HybridRetriever:
        def __init__(self):
            self.search_kwargs = {"k": k}

        def invoke(self, query: str) -> list[Document]:
            _k = self.search_kwargs.get("k", k)
            bm25_results = bm25_retriever.invoke(query)
            vector_results = vector_retriever.invoke(query)

            # RRF: score each doc by reciprocal rank in each retriever
            scores: dict[str, float] = {}
            docs_map: dict[str, Document] = {}

            for rank, doc in enumerate(bm25_results):
                key = doc.page_content[:100]
                scores[key] = scores.get(key, 0.0) + _rrf_score(rank)
                docs_map[key] = doc

            for rank, doc in enumerate(vector_results):
                key = doc.page_content[:100]
                scores[key] = scores.get(key, 0.0) + _rrf_score(rank)
                docs_map[key] = doc

            sorted_keys = sorted(scores, key=lambda x: scores[x], reverse=True)
            return [docs_map[key] for key in sorted_keys[:_k]]

    return HybridRetriever()
