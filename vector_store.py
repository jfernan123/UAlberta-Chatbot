# vector_store.py
from langchain_openai import OpenAIEmbeddings
from langchain.vectorstores import Chroma

def create_vector_db(chunks):
    embeddings = OpenAIEmbeddings()

    db = Chroma.from_texts(
        chunks,
        embedding=embeddings,
        persist_directory="db"
    )

    db.persist()
    return db