# vector_store.py
import shutil
import os
from langchain_chroma import Chroma
from .embeddings import get_embeddings


def create_vector_db(chunks, persist_directory="db"):
    embeddings = get_embeddings()

    # Try to delete the old db to rebuild from scratch
    if os.path.exists(persist_directory):
        try:
            shutil.rmtree(persist_directory)
        except PermissionError:
            # Windows: file locked by another process; use a fresh collection name
            # by removing all documents via Chroma client
            try:
                import chromadb
                client = chromadb.PersistentClient(path=persist_directory)
                for col in client.list_collections():
                    client.delete_collection(col.name)
            except Exception:
                pass  # if that fails too, Chroma.from_texts will append

    db = Chroma.from_texts(chunks, embedding=embeddings, persist_directory=persist_directory)

    return db
