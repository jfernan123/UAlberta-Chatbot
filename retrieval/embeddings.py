# Change this to "openai" to use OpenAI text-embedding-3-small
# Change this to "ollama" to use local nomic-embed-text (default)
EMBEDDING_PROVIDER = "ollama"


def get_embeddings():
    if EMBEDDING_PROVIDER == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model="text-embedding-3-small")

    from langchain_ollama import OllamaEmbeddings
    return OllamaEmbeddings(model="nomic-embed-text")
