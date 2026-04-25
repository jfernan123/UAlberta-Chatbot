import os
import shutil
from langchain_chroma import Chroma
from langchain_core.documents import Document
from .embeddings import get_embeddings


def create_vector_db(documents: list[Document], persist_directory: str = "db") -> Chroma:
    if os.path.exists(persist_directory):
        try:
            shutil.rmtree(persist_directory)
        except PermissionError:
            # Windows: DB files may be locked by another process; clear via Chroma client
            try:
                import chromadb
                client = chromadb.PersistentClient(path=persist_directory)
                for col in client.list_collections():
                    client.delete_collection(col.name)
            except Exception:
                pass  # Chroma.from_documents will overwrite below

    db = Chroma.from_documents(
        documents=documents,
        embedding=get_embeddings(),
        persist_directory=persist_directory,
    )
    return db
