# chatbot.py
import json
import re
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import HumanMessage, AIMessage
from langchain.tools import tool
from retriever import load_retriever
from course_tools import (
    get_stat_courses,
    get_math_courses,
    get_course_prerequisites,
    get_course_sequence,
    search_courses,
    get_courses_by_level,
)

# Shared conversation memory (across all users, limited to 10 messages)
# Manual implementation instead of langchain.memory (v0.3+ changed this)
_shared_history = []  # List of {"question": str, "answer": str}
MAX_HISTORY = 10


def _add_to_history(question: str, answer: str):
    """Add a Q&A pair to shared history."""
    _shared_history.append({"question": question, "answer": answer})
    # Keep only last MAX_HISTORY pairs
    if len(_shared_history) > MAX_HISTORY:
        _shared_history.pop(0)


def _get_history_str() -> str:
    """Get formatted history string."""
    if not _shared_history:
        return "No previous conversation."

    lines = []
    for i, item in enumerate(_shared_history, 1):
        lines.append(f"Turn {i}:")
        lines.append(f"  User: {item['question']}")
        lines.append(f"  Assistant: {item['answer'][:200]}...")  # Truncate for context
    return "\n".join(lines)


# Case-insensitivity mapping for common variations
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
    """Normalize query to handle common case/spelling variations."""
    normalized = query
    for pattern, replacement in QUERY_VARIATIONS:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return normalized


def extract_course_codes(query: str) -> list:
    """Extract course codes from a query."""
    import re

    pattern = r"\b(MATH|STAT)\s*(\d{3})\b"
    matches = re.findall(pattern, query, re.IGNORECASE)
    return [f"{prefix.upper()} {num}" for prefix, num in matches]


def detect_course_tools(query: str) -> list:
    """Detect which course tools should be called based on query keywords."""
    query_lower = query.lower()
    tools_to_call = []
    course_codes = extract_course_codes(query)

    # Prerequisite queries have highest priority (needs course code)
    prereq_keywords = [
        "prerequisite",
        "prereq",
        "require",
        "before i take",
        "before taking",
        "need before",
    ]
    if any(kw in query_lower for kw in prereq_keywords) and course_codes:
        tools_to_call.append(get_course_prerequisites)
        return tools_to_call  # Prioritize prereq over general course queries

    # Sequence/pathway queries
    seq_keywords = ["sequence", "path", "stream", "track", "after completing"]
    if any(kw in query_lower for kw in seq_keywords):
        tools_to_call.append(get_course_sequence)
        return tools_to_call

    # Statistics course queries
    stat_keywords = [
        "statistic",
        "statistics",
        "stat ",
        "stat",
        "data science",
        "biostat",
        "probability",
    ]
    if any(kw in query_lower for kw in stat_keywords):
        tools_to_call.append(get_stat_courses)

    # Year level queries - check BEFORE math_keywords (to catch "100-level math" etc)
    year_keywords = [
        "first year",
        "second year",
        "third year",
        "yr1",
        "yr2",
        "yr3",
        "100-level",
        "100 level",
        "200-level",
        "200 level",
        "300-level",
        "300 level",
        "year 1",
        "year 2",
        "year 3",
    ]
    for kw in year_keywords:
        if kw in query_lower:
            tools_to_call = [get_courses_by_level]
            return tools_to_call

    # Math course queries
    math_keywords = [
        "math ",
        "mathematic",
        "calculus",
        "algebra",
        "analysis",
        "geometry",
    ]
    if any(kw in query_lower for kw in math_keywords):
        # NEW: If a specific course code is mentioned and user is asking "what is X",
        # prioritize getting specific course info instead of listing all courses
        if course_codes and any(
            kw in query_lower
            for kw in ["what is", "what's", "details", "about", "name of"]
        ):
            # User is asking about a specific course - get that course's details
            tools_to_call = [get_course_prerequisites]
            return tools_to_call
        tools_to_call.append(get_math_courses)

    # Search queries (fallback)
    search_keywords = ["search", "find", "look for", "offered", "without any prereq"]
    if any(kw in query_lower for kw in search_keywords):
        tools_to_call.append(search_courses)

    # Senior/Graduate level course queries - check BEFORE general math/stat keywords
    senior_keywords = ["senior", "400-level", "yr4", "yr 4", "fourth year"]
    grad_keywords = ["graduate", "grad ", "500-level", "yr5", "yr 5", "500 level"]
    if any(kw in query_lower for kw in senior_keywords + grad_keywords):
        level = (
            "senior" if any(kw in query_lower for kw in senior_keywords) else "graduate"
        )
        tools_to_call = [get_courses_by_level]
        return tools_to_call

    return tools_to_call


def call_course_tools(query: str) -> str:
    """Call appropriate course tools based on query."""
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
                # Use first course code found, or default
                code = course_codes[0] if course_codes else None
                if code:
                    result = tool_func.invoke({"course_code": code})
                else:
                    result = "No specific course code found in question."
            elif tool_func == get_course_sequence:
                # Try to extract sequence name from query
                seq = extract_sequence_from_query(query)
                result = tool_func.invoke({"sequence_name": seq})
            elif tool_func == search_courses:
                # Extract keyword from query
                keyword = extract_search_keyword(query)
                result = tool_func.invoke({"keyword": keyword})
            elif tool_func == get_courses_by_level:
                # Determine department and level from query
                q = query.lower()
                # Check for year level
                if any(
                    kw in q
                    for kw in ["first year", "100-level", "100 level", "yr1", "year 1"]
                ):
                    level = "first"
                elif any(
                    kw in q
                    for kw in ["second year", "200-level", "200 level", "yr2", "year 2"]
                ):
                    level = "second"
                elif any(
                    kw in q
                    for kw in ["third year", "300-level", "300 level", "yr3", "year 3"]
                ):
                    level = "third"
                elif any(
                    kw in q
                    for kw in ["senior", "400-level", "400 level", "yr4", "fourth year"]
                ):
                    level = "senior"
                elif any(
                    kw in q
                    for kw in ["graduate", "grad ", "500-level", "500 level", "yr5"]
                ):
                    level = "graduate"
                else:
                    level = "graduate"  # default
                # Determine department
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
    """Extract sequence name from query."""
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

    # NEW: Detect sequence from course code in query (Option A)
    course_codes = extract_course_codes(query)
    if course_codes:
        # Map course to its sequence
        course_to_seq = {
            "MATH 117": "honors",
            "MATH 118": "honors",
            "MATH 216": "honors",
            "MATH 217": "honors",
            "MATH 100": "engineering",
            "MATH 101": "engineering",
            "MATH 209": "engineering",
            "MATH 134": "regular_life_sci",
            "MATH 136": "regular_life_sci",
            "MATH 144": "regular_math_phys",
            "MATH 146": "regular_math_phys",
            "MATH 154": "regular_business",
            "MATH 156": "regular_business",
        }
        if course_codes[0] in course_to_seq:
            return course_to_seq[course_codes[0]]

    return None


def extract_search_keyword(query: str) -> str:
    """Extract search keyword from query."""
    query_lower = query.lower()
    # Common patterns for searching
    patterns = [
        r"courses (?:about|covering|dealing with|matching) (\w+)",
        r"courses (?:in|about|for) (\w+)",
        r"what courses (?:cover|deal with|match) (\w+)",
    ]

    import re

    for pattern in patterns:
        match = re.search(pattern, query_lower)
        if match:
            return match.group(1)

    return query_lower.split()[-1] if query_lower.split() else "calculus"


def build_chatbot():
    retriever = load_retriever()
    llm = ChatOllama(model="qwen3:0.6b", temperature=0)

    # Use shared conversation history across all users
    get_history = _get_history_str
    add_to_history = _add_to_history

    prompt = ChatPromptTemplate.from_template("""
You are a helpful assistant for the University of Alberta Math & Statistics department.
Answer questions based on the course information and context provided.

Chat History (previous conversation):
{chat_history}

IMPORTANT INSTRUCTIONS:
1. When the Course Information section contains specific details about courses (like prerequisites, course names, or sequences), you MUST use that information to answer the question.
2. Do NOT say a course is not listed when it appears in the Course Information.
3. Do NOT make up course names or numbers - only use courses that appear in the Course Information section.
4. If the Course Information mentions specific courses (like MATH 118 or MATH 217), include them in your answer.
5. When listing Statistics (STAT) courses, note that many require MATH prerequisites - include MATH courses that appear in the Course Information as they may be required prerequisites.
6. Previous user answers are in data/feedback.json. Study these to craft your response.

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

Answer:
""")

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    def build_input(question):
        # Detect course tools BEFORE normalization (to preserve STAT/STAT keywords)
        course_info = call_course_tools(question)

        # Normalize query for retrieval
        normalized_q = normalize_query(question)

        docs = retriever.invoke(normalized_q)
        context = "\n\n".join(doc.page_content for doc in docs)

        if not course_info:
            course_info = "No specific course information available for this query."

        return {
            "context": context,
            "course_info": course_info,
            "question": normalized_q,
        }, docs

    def run_chain(question):
        # Get course info BEFORE normalization (preserves STAT/MATH keywords)
        course_info = call_course_tools(question)

        # Then normalize for retrieval
        normalized_q = normalize_query(question)

        docs = retriever.invoke(normalized_q)
        context = "\n\n".join(doc.page_content for doc in docs)

        if not course_info:
            course_info = "No specific course information available for this query."

        # Load chat history from shared memory
        history_str = get_history()

        inputs = {
            "chat_history": history_str,
            "context": context,
            "course_info": course_info,
            "question": normalized_q,
        }
        answer = (prompt | llm | StrOutputParser()).invoke(inputs)

        # Save to shared history
        add_to_history(question, answer)

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
