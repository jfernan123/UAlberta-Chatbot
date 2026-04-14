# chatbot.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from retriever import load_retriever


def build_chatbot():
    retriever = load_retriever()
    llm = ChatOllama(model="qwen3:0.6b", temperature=0)

    prompt = ChatPromptTemplate.from_template("""
    Answer the question based only on the context below.

    Context:
    {context}

    Question:
    {question}
    """)

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    def build_input(question):
        docs = retriever.invoke(question)
        context = "\n\n".join(doc.page_content for doc in docs)
        return {"context": context, "question": question}, docs

    def run_chain(question):
        inputs, docs = build_input(question)
        answer = (prompt | llm | StrOutputParser()).invoke(inputs)
        return answer

    return run_chain


if __name__ == "__main__":
    bot = build_chatbot()

    while True:
        query = input("Ask a question: ")

        result = bot(query)

        print("\nAnswer:")
        print(result)
