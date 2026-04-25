import os
from langchain_core.embeddings import Embeddings

# Override with EMBEDDING_PROVIDER env var: "ollama", "sentence", or "openai"
EMBEDDING_PROVIDER = os.environ.get("EMBEDDING_PROVIDER", "ollama")

_embeddings = None


def get_embeddings() -> Embeddings:
    global _embeddings
    if _embeddings is not None:
        return _embeddings

    if EMBEDDING_PROVIDER == "openai":
        from langchain_openai import OpenAIEmbeddings
        _embeddings = OpenAIEmbeddings(model="text-embedding-3-small")

    elif EMBEDDING_PROVIDER == "sentence":
        from sentence_transformers import SentenceTransformer

        class BGEEmbeddings(Embeddings):
            def __init__(self):
                self._model = SentenceTransformer("BAAI/bge-small-en-v1.5")

            def embed_documents(self, texts: list[str]) -> list[list[float]]:
                return self._model.encode(texts, normalize_embeddings=True).tolist()

            def embed_query(self, text: str) -> list[float]:
                return self._model.encode(text, normalize_embeddings=True).tolist()

        _embeddings = BGEEmbeddings()

    else:
        # Default: nomic-embed-text via Ollama (free, no GPU needed)
        from langchain_ollama import OllamaEmbeddings
        _embeddings = OllamaEmbeddings(model="nomic-embed-text")

    return _embeddings
