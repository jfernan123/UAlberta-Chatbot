# retriever.py
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings


def load_retriever(k: int = 5):
    """Load retriever with configurable k (default 5)"""
    db = Chroma(
        persist_directory="db",
        embedding_function=OllamaEmbeddings(model="nomic-embed-text"),
    )

    return db.as_retriever(search_kwargs={"k": k})
