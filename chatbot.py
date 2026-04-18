# chatbot.py
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from retriever import load_retriever

# Query expansion: add relevant course codes for statistics queries
QUERY_EXPANSION = {
    "statistics": "STAT 151 STAT 252 STAT 265 STAT 266 MATH 117 MATH 125",
    "mathematics": "MATH 117 MATH 118 MATH 125 MATH 127 STAT 151",
    "linear algebra": "MATH 125 MATH 127",
    "calculus": "MATH 117 MATH 118 MATH 144",
    "first year": "MATH 117 MATH 125 STAT 151 CMPUT 174",
}


def expand_query(question):
    """Expand question with relevant course codes"""
    q_lower = question.lower()
    expanded = question
    
    for key, courses in QUERY_EXPANSION.items():
        if key in q_lower:
            expanded = f"{question} {courses}"
            break
    
    return expanded


def build_chatbot():
    retriever = load_retriever(k=5)
    llm = ChatOllama(model="qwen3:0.6b", temperature=0)

    prompt = ChatPromptTemplate.from_template("""
    Answer the question based only on the context below.

    Context:
    {context}

    Question:
    {question}
    """)

    def build_input(question):
        # Expand query with course codes
        expanded_q = expand_query(question)
        docs = retriever.invoke(expanded_q)
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
        try:
            query = input("Ask a question: ")
            if not query.strip():
                break

            result = bot(query)

            print("\nAnswer:")
            print(result)
        except EOFError:
            break
        except KeyboardInterrupt:
            print("\nExiting...")
            break
