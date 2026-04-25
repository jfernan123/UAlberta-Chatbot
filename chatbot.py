import os
import re
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from retrieval import load_retriever
from courses.course_tools import (
    get_stat_courses,
    get_math_courses,
    get_course_prerequisites,
    get_course_sequence,
    search_courses,
    get_courses_by_level,
)

# Override with LLM_PROVIDER env var: "ollama" or "claude"
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama")

# Set to False to disable course tool detection and rely purely on vector DB
USE_COURSE_TOOLS = True

# Set to True to print retrieved chunks and course tool output before each answer
VERBOSE = False

# Set to False to disable query normalisation (e.g. "stat" -> "Statistics")
USE_NORMALIZATION = True


def _get_llm():
    if LLM_PROVIDER == "claude":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
    return ChatOllama(model="qwen3:0.6b", temperature=0, think=False)


# Shared conversation memory (last 10 Q&A pairs across the session)
_shared_history: list[dict] = []
MAX_HISTORY = 10


def _add_to_history(question: str, answer: str) -> None:
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


def _strip_thinking(text: str) -> str:
    """Remove <think>...</think> blocks emitted by qwen3 models."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


# Case-insensitivity mapping for common query variations
QUERY_VARIATIONS = [
    (r"\bmdp\b", "MDP"),
    (r"\bhonours?\b", "Honors"),
    (r"\bstats\b", "Statistics"),
    (r"\bmaths\b", "Mathematics"),
    (r"\bundergrad\b", "undergraduate"),
    (r"\bmath(?!ematics)\b", "Mathematics"),
    (r"\bstat(?!istics)\b", "Statistics"),
    (r"\byr1\b", "Year 1"),
    (r"\byr2\b", "Year 2"),
    (r"\byr3\b", "Year 3"),
    (r"\byr4\b", "Year 4"),
    (r"\b1st year\b", "first year"),
    (r"\b2nd year\b", "second year"),
    (r"\b3rd year\b", "third year"),
    (r"\b4th year\b", "fourth year"),
    (r"\bundergraduateuate\b", "undergraduate"),
]


def normalize_query(query: str) -> str:
    normalized = query
    for pattern, replacement in QUERY_VARIATIONS:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return normalized


def extract_course_codes(query: str) -> list[str]:
    pattern = r"\b(MATH|STAT)\s*(\d{3})\b"
    matches = re.findall(pattern, query, re.IGNORECASE)
    return [f"{prefix.upper()} {num}" for prefix, num in matches]


def detect_course_tools(query: str) -> list:
    query_lower = query.lower()
    tools_to_call = []
    course_codes = extract_course_codes(query)

    # Program/degree/admission and comparison queries should be answered from retrieved
    # pages, not from the course-listing tools (which return course codes, not descriptions).
    program_keywords = [
        "degree program", "graduate program", "undergraduate program",
        "admission", "apply", "applying",
        "phd", "msc", "master", "mmath", "requirements to get in",
        "how to get into", "graduate studies", "postgraduate",
        # comparison / structural questions
        "difference between", "honors vs", "major vs", "honors and major",
        "what is the difference", "compare", "program structure",
        "double major", "can i double",
        # specific named programs / services
        "what is the mdp", "what is the msc", "what is the phd",
        "decima robinson",
    ]
    if any(kw in query_lower for kw in program_keywords):
        return []

    prereq_keywords = ["prerequisite", "prereq", "require", "before i take", "before taking", "need before"]
    if any(kw in query_lower for kw in prereq_keywords) and course_codes:
        return [get_course_prerequisites]

    seq_keywords = ["sequence", "path", "stream", "track", "after completing"]
    if any(kw in query_lower for kw in seq_keywords):
        return [get_course_sequence]

    stat_keywords = ["statistic", "statistics", "stat ", "stat", "data science", "biostat", "probability"]
    if any(kw in query_lower for kw in stat_keywords):
        tools_to_call.append(get_stat_courses)

    year_keywords = [
        "first year", "second year", "third year", "yr1", "yr2", "yr3",
        "100-level", "100 level", "200-level", "200 level", "300-level", "300 level",
        "year 1", "year 2", "year 3",
    ]
    for kw in year_keywords:
        if kw in query_lower:
            return [get_courses_by_level]

    math_keywords = ["math ", "mathematic", "calculus", "algebra", "analysis", "geometry"]
    if any(kw in query_lower for kw in math_keywords):
        if course_codes and any(kw in query_lower for kw in ["what is", "what's", "details", "about", "name of"]):
            return [get_course_prerequisites]
        tools_to_call.append(get_math_courses)

    search_keywords = ["search", "find", "look for", "offered", "without any prereq"]
    if any(kw in query_lower for kw in search_keywords):
        tools_to_call.append(search_courses)

    senior_keywords = ["senior", "400-level", "yr4", "yr 4", "fourth year"]
    grad_keywords = ["graduate", "grad ", "500-level", "yr5", "yr 5", "500 level"]
    if any(kw in query_lower for kw in senior_keywords + grad_keywords):
        return [get_courses_by_level]

    return tools_to_call


GRADUATE_PROGRAMS_INFO = """The Department of Mathematical and Statistical Sciences at the University of Alberta offers the following graduate programs:

1. MDP — Master's in Modelling, Data + Predictions (course-based, 16 months): A professionally-oriented data science program combining data modelling and analytics skills for careers in industry and government.

2. Thesis-based MSc (Master of Science): Typically two years. Natural stepping stone to a PhD. Available with specializations in Applied Mathematics, Mathematical Finance, Mathematical Physics, Pure Mathematics, Statistical Machine Learning, and Statistics.

3. PhD (Doctoral Program): Typically four to five years. Normally requires a thesis-based MSc for entry; very strong BSc students may transfer directly. Same specializations as the MSc.

4. Embedded Certificate in Data Science: Supplementary to a Pure/Applied Mathematics or Mathematical Physics degree. Provides marketable skills for the non-academic job market.

5. Graduate Teaching and Learning Program: A supplementary post-baccalaureate certificate in university teaching instruction, open to all graduate students.

Specializations available in MSc and PhD programs: Applied Mathematics, Mathematical Finance, Mathematical Physics, (Pure) Mathematics, Statistical Machine Learning, Statistics.

Source: https://www.ualberta.ca/en/mathematical-and-statistical-sciences/graduate-studies/programs/index.html"""

GRADUATE_CONTACT_INFO = """Graduate program contacts for the Department of Mathematical and Statistical Sciences at the University of Alberta:

- MDP Program (Modelling, Data + Predictions): Jane Cooper (UCOMM 5-182F), email mssmdp@ualberta.ca. Jane Cooper is the coordinator and person in charge of the MDP program.
- All other graduate programs (MSc, PhD): Amy Ouyang (UCOMM 5-182G), email mssgrad@ualberta.ca, phone 780-492-5799.
- Prospective student inquiries (any program): sci.gradadm@ualberta.ca

Source: https://www.ualberta.ca/en/mathematical-and-statistical-sciences/graduate-studies/contact.html"""


def _detect_graduate_info_query(query: str) -> str:
    """Return direct info string for graduate program listing or contact queries, else empty string."""
    q = query.lower()
    listing_keywords = [
        "what graduate programs", "which graduate programs", "graduate programs available",
        "available graduate programs", "list graduate programs", "graduate programs offered",
        "what grad programs", "grad programs available", "which grad programs",
        "programs in math and stat", "programs offered in math", "graduate degrees available",
        "what programs does", "what degrees",
    ]
    contact_keywords = [
        "who is in charge", "who runs", "who manages", "who leads", "who coordinates",
        "who is responsible", "contact for mdp", "mdp contact", "mdp coordinator",
        "in charge of the mdp", "who to contact", "who should i contact",
    ]
    if any(kw in q for kw in listing_keywords):
        return GRADUATE_PROGRAMS_INFO
    if any(kw in q for kw in contact_keywords):
        return GRADUATE_CONTACT_INFO
    return ""


def call_course_tools(query: str) -> str:
    if not USE_COURSE_TOOLS:
        return ""

    graduate_info = _detect_graduate_info_query(query)
    if graduate_info:
        return graduate_info

    tools_to_call = detect_course_tools(query)
    course_codes = extract_course_codes(query)

    if not tools_to_call:
        return ""

    results = []
    for tool_func in tools_to_call:
        try:
            if tool_func == get_stat_courses:
                result = tool_func.invoke({})
            elif tool_func == get_math_courses:
                result = tool_func.invoke({})
            elif tool_func == get_course_prerequisites:
                code = course_codes[0] if course_codes else None
                if code:
                    result = tool_func.invoke({"course_code": code})
                else:
                    result = "No specific course code found in question."
            elif tool_func == get_course_sequence:
                seq = extract_sequence_from_query(query)
                result = tool_func.invoke({"sequence_name": seq})
            elif tool_func == search_courses:
                keyword = extract_search_keyword(query)
                result = tool_func.invoke({"keyword": keyword})
            elif tool_func == get_courses_by_level:
                q = query.lower()
                if any(kw in q for kw in ["first year", "100-level", "100 level", "yr1", "year 1"]):
                    level = "first"
                elif any(kw in q for kw in ["second year", "200-level", "200 level", "yr2", "year 2"]):
                    level = "second"
                elif any(kw in q for kw in ["third year", "300-level", "300 level", "yr3", "year 3"]):
                    level = "third"
                elif any(kw in q for kw in ["senior", "400-level", "400 level", "yr4", "fourth year"]):
                    level = "senior"
                else:
                    level = "graduate"
                dept = None
                if "math" in query.lower():
                    dept = "math"
                elif "stat" in query.lower():
                    dept = "stat"
                result = tool_func.invoke({"department": dept, "level": level})
            else:
                result = ""

            if result:
                results.append(result)
        except Exception as e:
            results.append(f"Error calling {tool_func.name}: {e}")

    return "\n\n".join(results)


def extract_sequence_from_query(query: str) -> str | None:
    query_lower = query.lower()
    sequences = {
        "engineering": ["engineering"],
        "honors": ["honors", "honour"],
        "regular_life_sci": ["life sci", "life science"],
        "regular_math_phys": ["math phys", "physical science"],
        "regular_business": ["business", "economics"],
        "applied_stats": ["applied stat"],
        "probability": ["probability"],
    }
    for seq_name, keywords in sequences.items():
        if any(kw in query_lower for kw in keywords):
            return seq_name

    course_codes = extract_course_codes(query)
    if course_codes:
        course_to_seq = {
            "MATH 117": "honors", "MATH 118": "honors",
            "MATH 216": "honors", "MATH 217": "honors",
            "MATH 100": "engineering", "MATH 101": "engineering", "MATH 209": "engineering",
            "MATH 134": "regular_life_sci", "MATH 136": "regular_life_sci",
            "MATH 144": "regular_math_phys", "MATH 146": "regular_math_phys",
            "MATH 154": "regular_business", "MATH 156": "regular_business",
        }
        if course_codes[0] in course_to_seq:
            return course_to_seq[course_codes[0]]

    return None


def extract_search_keyword(query: str) -> str:
    query_lower = query.lower()
    patterns = [
        r"courses (?:about|covering|dealing with|matching) (\w+)",
        r"courses (?:in|about|for) (\w+)",
        r"what courses (?:cover|deal with|match) (\w+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, query_lower)
        if match:
            return match.group(1)
    return query_lower.split()[-1] if query_lower.split() else "calculus"


def build_chatbot():
    retriever = load_retriever()
    llm = _get_llm()

    prompt = ChatPromptTemplate.from_template("""You are a helpful assistant for the University of Alberta Math & Statistics department.
Answer questions based on the course information and context provided.

Chat History (previous conversation):
{chat_history}

IMPORTANT INSTRUCTIONS:
1. When the Course Information section contains specific details about courses (like prerequisites, course names, or sequences), you MUST use that information to answer the question.
2. Do NOT say a course is not listed when it appears in the Course Information.
3. Do NOT make up course names or numbers - only use courses that appear in the Course Information section.
4. If the Course Information mentions specific courses (like MATH 118 or MATH 217), include them in your answer.
5. When listing Statistics (STAT) courses, note that many require MATH prerequisites - include MATH courses that appear in the Course Information as they may be required prerequisites.
6. When the Course Information contains a list of courses, reproduce ALL of them in your answer — do not stop after the first few. Every course in the list matters.

IMPORTANT TERMINOLOGY CLARIFICATION:
- "Undergraduate" in this context refers to COURSE LEVEL (100-400 level), NOT first-year students
- "Graduate" refers to 500+ level courses
- Course numbers indicate year level: 100-level = Year 1, 200-level = Year 2, etc.
- "Fall/Winter" refers to SEMESTER (Fall term, Winter term), NOT years in a program
- When users ask about "first year courses", look for 100-level courses
- When users ask about "second year courses", look for 200-level courses
- When users ask about "help", "support", "tutoring", or "services" for math/stats students, you MUST mention the Decima Robinson Support Centre - it is the main student support service

Course Information:
{course_info}

Main Context (from department website):
{context}

Question:
{question}

Answer:""")

    def run_chain(question: str):
        normalized_q = normalize_query(question) if USE_NORMALIZATION else question
        course_info = call_course_tools(normalized_q)
        docs = retriever.invoke(normalized_q)

        if VERBOSE:
            print(f"\n--- Retrieved {len(docs)} chunks ---")
            for i, doc in enumerate(docs, 1):
                print(f"\n[{i}] {doc.page_content[:200]}")
            print(f"\n--- Course tool output ---\n{course_info}\n" + "-" * 40)
        context = "\n\n".join(doc.page_content for doc in docs)

        if not course_info:
            course_info = "No specific course information available for this query."

        inputs = {
            "chat_history": _get_history_str(),
            "context": context,
            "course_info": course_info,
            "question": normalized_q,
        }

        chain = prompt | llm | StrOutputParser()
        full_response = ""
        for chunk in chain.stream(inputs):
            full_response += chunk
            yield chunk

        # Append deduplicated source links after the LLM response
        seen_urls: set[str] = set()
        source_urls: list[str] = []
        for doc in docs:
            url = doc.metadata.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                source_urls.append(url)
            if len(source_urls) == 3:
                break

        if source_urls:
            source_block = "\n\n---\n**Sources**\n" + "\n".join(
                f"- [{url}]({url})" for url in source_urls
            )
            yield source_block

        # Save to history without the source block so it doesn't inflate context
        _add_to_history(question, _strip_thinking(full_response))

    return run_chain


if __name__ == "__main__":
    bot = build_chatbot()
    while True:
        try:
            query = input("Ask a question: ")
            if not query.strip():
                break
            for chunk in bot(query):
                print(chunk, end="", flush=True)
            print()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break
