# vector_store.py
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma


def create_vector_db(chunks):
    embeddings = OllamaEmbeddings(model="nomic-embed-text")

    db = Chroma.from_texts(chunks, embedding=embeddings, persist_directory="db")

    return db
