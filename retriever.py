# retriever.py
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

def load_retriever():
    db = Chroma(
        persist_directory="db",
        embedding_function=OpenAIEmbeddings()
    )

    return db.as_retriever(search_kwargs={"k": 4})