from langchain_core.embeddings import Embeddings

# Switch to "openai" to use OpenAI text-embedding-3-small instead.
EMBEDDING_PROVIDER = "local"

_embeddings = None


def get_embeddings() -> Embeddings:
    global _embeddings
    if _embeddings is not None:
        return _embeddings

    if EMBEDDING_PROVIDER == "openai":
        from langchain_openai import OpenAIEmbeddings
        _embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        return _embeddings

    # Default: BAAI/bge-small-en-v1.5 via sentence-transformers (no Ollama needed)
    from sentence_transformers import SentenceTransformer

    class BGEEmbeddings(Embeddings):
        def __init__(self):
            self._model = SentenceTransformer("BAAI/bge-small-en-v1.5")

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return self._model.encode(texts, normalize_embeddings=True).tolist()

        def embed_query(self, text: str) -> list[float]:
            return self._model.encode(text, normalize_embeddings=True).tolist()

    _embeddings = BGEEmbeddings()
    return _embeddings
