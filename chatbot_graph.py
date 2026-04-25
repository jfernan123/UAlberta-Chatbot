# chatbot_graph.py
# LangGraph-based RAG chatbot. Keeps chatbot.py untouched.
import re
from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from retrieval import load_retriever
from courses.course_tools import (
    get_stat_courses,
    get_math_courses,
    get_course_prerequisites,
    get_course_sequence,
    search_courses,
    get_courses_by_level,
    get_program_requirements,
)

LLM_PROVIDER = "claude"
VERBOSE = False
MAX_RETRIEVAL_ATTEMPTS = 2


def _get_llm():
    if LLM_PROVIDER == "claude":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
    from langchain_ollama import ChatOllama
    return ChatOllama(model="qwen3:0.6b", temperature=0)


# --------------------------------------------------------------------------- #
# Shared conversation memory                                                    #
# --------------------------------------------------------------------------- #
_shared_history: list[dict] = []
MAX_HISTORY = 10


def _add_to_history(question: str, answer: str):
    _shared_history.append({"question": question, "answer": answer})
    if len(_shared_history) > MAX_HISTORY:
        _shared_history.pop(0)


def _get_history_str() -> str:
    if not _shared_history:
        return "No previous conversation."
    lines = []
    for i, item in enumerate(_shared_history, 1):
        lines.append(f"Turn {i}:")
        lines.append(f"  User: {item['question']}")
        lines.append(f"  Assistant: {item['answer'][:200]}...")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Graph state                                                                   #
# --------------------------------------------------------------------------- #
class RAGState(TypedDict):
    question: str
    query_type: str        # set by classify node
    refined_query: str     # may be rewritten after a failed grade
    context: str           # from vector retriever
    course_info: str       # from structured course tools
    chat_history: str
    answer: str
    attempts: int


# --------------------------------------------------------------------------- #
# Helper: extract course codes                                                  #
# --------------------------------------------------------------------------- #
def _extract_course_codes(query: str) -> list[str]:
    matches = re.findall(r"\b(MATH|STAT)\s*(\d{3})\b", query, re.IGNORECASE)
    return [f"{p.upper()} {n}" for p, n in matches]


# --------------------------------------------------------------------------- #
# Node 1: classify                                                              #
# --------------------------------------------------------------------------- #
_CLASSIFY_PROMPT = ChatPromptTemplate.from_template("""
You are a query classifier for a university Math & Statistics department chatbot.
Classify the user question into EXACTLY ONE of these categories:

- prereq        : asking for prerequisites or requirements of a specific course (e.g. "prereqs for STAT 471")
- courses       : asking for a list of courses (e.g. "what 400-level STAT courses are there", "first year math courses")
- program_req   : asking about degree/program requirements (e.g. "honors math requirements", "what do I need for the major")
- admissions    : asking how to apply or admission requirements for a graduate program (MSc, PhD, MDP)
- support       : asking about tutoring, help centres, student services
- general       : anything else (program descriptions, comparisons, faculty info, etc.)

Reply with ONLY the category label, nothing else.

Question: {question}
""")


def classify_node(state: RAGState) -> RAGState:
    llm = _get_llm()
    chain = _CLASSIFY_PROMPT | llm | StrOutputParser()
    raw = chain.invoke({"question": state["question"]}).strip().lower()

    valid = {"prereq", "courses", "program_req", "admissions", "support", "general"}
    query_type = raw if raw in valid else "general"

    if VERBOSE:
        print(f"\n[classify] → {query_type}")

    return {**state, "query_type": query_type, "refined_query": state["question"], "attempts": 0}


# --------------------------------------------------------------------------- #
# Node 2: retrieve                                                              #
# --------------------------------------------------------------------------- #
def retrieve_node(state: RAGState) -> RAGState:
    retriever = load_retriever()
    query = state["refined_query"]
    query_type = state["query_type"]
    course_codes = _extract_course_codes(query)
    query_lower = query.lower()

    # --- structured course tool call ---
    course_info = ""
    try:
        if query_type == "prereq" and course_codes:
            course_info = get_course_prerequisites.invoke({"course_code": course_codes[0]})

        elif query_type == "courses":
            dept = None
            if "math" in query_lower:
                dept = "math"
            elif "stat" in query_lower:
                dept = "stat"

            level = None
            if any(kw in query_lower for kw in ["first year", "100-level", "100 level", "year 1"]):
                level = "first"
            elif any(kw in query_lower for kw in ["second year", "200-level", "200 level", "year 2"]):
                level = "second"
            elif any(kw in query_lower for kw in ["third year", "300-level", "300 level", "year 3"]):
                level = "third"
            elif any(kw in query_lower for kw in ["senior", "400-level", "400 level", "fourth year"]):
                level = "senior"
            elif any(kw in query_lower for kw in ["graduate", "500-level", "500 level"]):
                level = "graduate"

            if level or dept:
                course_info = get_courses_by_level.invoke({"department": dept, "level": level})
            elif "stat" in query_lower:
                course_info = get_stat_courses.invoke({})
            elif "math" in query_lower:
                course_info = get_math_courses.invoke({})

        elif query_type == "program_req":
            q = query.lower()
            if "stat" in q:
                dept = "statistics"
            else:
                dept = "math"
            if "minor" in q:
                level = "minor"
            elif "major" in q:
                level = "major"
            else:
                level = "honors"
            course_info = get_program_requirements.invoke({"program": f"{level} {dept}"})

        elif query_type == "prereq" and not course_codes:
            # no code found — fall through to vector only
            pass

    except Exception as e:
        course_info = f"Course tool error: {e}"

    # --- vector retrieval ---
    docs = retriever.invoke(query)
    context = "\n\n".join(doc.page_content for doc in docs)

    if VERBOSE:
        print(f"[retrieve] {len(docs)} docs, course_info={bool(course_info)}")

    return {
        **state,
        "context": context,
        "course_info": course_info or "No specific course information available for this query.",
        "attempts": state["attempts"] + 1,
    }


# --------------------------------------------------------------------------- #
# Node 3: grade                                                                 #
# --------------------------------------------------------------------------- #
_GRADE_PROMPT = ChatPromptTemplate.from_template("""
You are grading whether the retrieved context is sufficient to answer the question.

Question: {question}

Retrieved context (first 1500 chars):
{context_preview}

Course info:
{course_info_preview}

Is this context sufficient to give a helpful, specific answer?
Reply with ONLY "sufficient" or "insufficient". No explanation.
""")


def grade_node(state: RAGState) -> RAGState:
    if state["attempts"] >= MAX_RETRIEVAL_ATTEMPTS:
        if VERBOSE:
            print("[grade] max attempts reached → sufficient")
        return {**state, "query_type": state["query_type"] + ":done"}

    llm = _get_llm()
    chain = _GRADE_PROMPT | llm | StrOutputParser()
    verdict = chain.invoke({
        "question": state["question"],
        "context_preview": state["context"][:1500],
        "course_info_preview": state["course_info"][:500],
    }).strip().lower()

    if VERBOSE:
        print(f"[grade] verdict={verdict}, attempt={state['attempts']}")

    if verdict == "sufficient":
        return {**state, "query_type": state["query_type"] + ":done"}

    # Rewrite query to be more specific before retrying
    rewrite_prompt = ChatPromptTemplate.from_template("""
The following query did not retrieve useful context. Rewrite it to be more specific
and likely to match relevant university course catalog text. Output ONLY the rewritten query.

Original: {question}
""")
    rewrite_chain = rewrite_prompt | llm | StrOutputParser()
    refined = rewrite_chain.invoke({"question": state["question"]}).strip()

    if VERBOSE:
        print(f"[grade] rewriting query → {refined}")

    return {**state, "refined_query": refined}


# --------------------------------------------------------------------------- #
# Node 4: generate                                                              #
# --------------------------------------------------------------------------- #
_ANSWER_PROMPT = ChatPromptTemplate.from_template("""
You are a helpful assistant for the University of Alberta Math & Statistics department.
Answer questions based on the course information and context provided.

Chat History:
{chat_history}

IMPORTANT INSTRUCTIONS:
1. When the Course Information section contains specific details, use it to answer.
2. Do NOT say a course is not listed when it appears in the Course Information.
3. Do NOT make up course names or numbers.
4. When users ask about "help", "support", or "tutoring", mention the Decima Robinson Support Centre.

TERMINOLOGY:
- 100-400 level = undergraduate courses; 500+ = graduate
- "Fall/Winter" = semester names, not years
- "Undergraduate" = course level, not student year

Course Information:
{course_info}

Context (from department website):
{context}

Question:
{question}

Answer:
""")


def _extract_sources(context: str, course_info: str, query_type: str) -> list[str]:
    """Pull unique source URLs out of retrieved context chunks."""
    urls = []
    for chunk in context.split("\n\n"):
        m = re.match(r"\[Source: (https?://[^\]]+)\]", chunk.strip())
        if m:
            url = m.group(1)
            if url not in urls:
                urls.append(url)

    # For structured tool results, note the data source
    if course_info and "No specific course information" not in course_info:
        label = None
        if query_type.startswith("prereq") or query_type.startswith("courses"):
            label = "Course database (data/course_graph.json)"
        elif query_type.startswith("program_req"):
            label = "UAlberta Academic Calendar (calendar.ualberta.ca)"
        if label and label not in urls:
            urls.append(label)

    return urls


def generate_node(state: RAGState) -> RAGState:
    llm = _get_llm()
    chain = _ANSWER_PROMPT | llm | StrOutputParser()
    answer = chain.invoke({
        "chat_history": state["chat_history"],
        "course_info": state["course_info"],
        "context": state["context"],
        "question": state["question"],
    })

    sources = _extract_sources(state["context"], state["course_info"], state["query_type"])
    if sources:
        source_lines = "\n".join(f"- {s}" for s in sources)
        answer += f"\n\n---\n**Sources:**\n{source_lines}"

    return {**state, "answer": answer}


# --------------------------------------------------------------------------- #
# Edge router: after grade, go back to retrieve or forward to generate          #
# --------------------------------------------------------------------------- #
def after_grade(state: RAGState) -> Literal["retrieve", "generate"]:
    if state["query_type"].endswith(":done"):
        return "generate"
    return "retrieve"


# --------------------------------------------------------------------------- #
# Build graph                                                                   #
# --------------------------------------------------------------------------- #
def _build_graph():
    g = StateGraph(RAGState)

    g.add_node("classify", classify_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("grade", grade_node)
    g.add_node("generate", generate_node)

    g.set_entry_point("classify")
    g.add_edge("classify", "retrieve")
    g.add_edge("retrieve", "grade")
    g.add_conditional_edges("grade", after_grade, {"retrieve": "retrieve", "generate": "generate"})
    g.add_edge("generate", END)

    return g.compile()


_graph = None


def build_chatbot():
    """Returns a run_chain(question) callable — same interface as chatbot.py."""
    global _graph
    if _graph is None:
        _graph = _build_graph()

    def run_chain(question: str) -> str:
        initial_state: RAGState = {
            "question": question,
            "query_type": "",
            "refined_query": question,
            "context": "",
            "course_info": "",
            "chat_history": _get_history_str(),
            "answer": "",
            "attempts": 0,
        }
        result = _graph.invoke(initial_state)
        answer = result["answer"]
        _add_to_history(question, answer)
        return answer

    return run_chain


if __name__ == "__main__":
    bot = build_chatbot()
    while True:
        try:
            query = input("Ask a question: ")
            if not query.strip():
                break
            print("\nAnswer:")
            print(bot(query))
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break
