# chatbot.py
import json
import re
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from retriever import load_retriever

# Case-insensitivity mapping for common variations
# Keys are regex patterns, values are replacement strings
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
    (r"\bundergraduateuate\b", "undergraduate"),  # Fix double undergrad
]


def normalize_query(query: str) -> str:
    """Normalize query to handle common case/spelling variations."""
    normalized = query
    for pattern, replacement in QUERY_VARIATIONS:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)
    return normalized


def load_course_graph():
    """Load course dependency graph."""
    try:
        with open("data/course_graph.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def get_course_info(course_code):
    """Look up course information from the course graph."""
    graph = load_course_graph()
    if not graph:
        return None
    return graph.get("courses", {}).get(course_code)


def get_course_prereqs(course_code):
    """Get prerequisites for a course."""
    course = get_course_info(course_code)
    if course:
        return course.get("alternatives", [])
    return []


def format_course_graph():
    """Format course graph for context."""
    graph = load_course_graph()
    if not graph:
        return "No course data available."

    year_labels = {
        0: "Graduate/Other",
        1: "Year 1",
        2: "Year 2",
        3: "Year 3",
        4: "Year 4",
    }

    lines = ["=== Course Information ==="]

    # Group courses by year level for better organization
    by_year = {}
    for code, info in graph.get("courses", {}).items():
        if not code.startswith(("MATH", "STAT")):
            continue
        year = info.get("year_level", 0)
        if year not in by_year:
            by_year[year] = []
        by_year[year].append((code, info))

    for year in sorted(by_year.keys()):
        year_label = year_labels.get(year, "Unknown")
        lines.append(f"\n--- {year_label} Courses ---")
        for code, info in sorted(by_year[year]):
            name = info.get("name", "Unknown")
            prereqs = info.get("prerequisites", [])
            seq = info.get("sequence", "")

            line = f"{code}: {name}"
            if seq:
                line += f" [{seq.replace('_', ' ')}]"
            lines.append(line)

            if prereqs:
                lines.append(f"  Prerequisites: {', '.join(prereqs)}")

    # Add sequence overview
    sequences = graph.get("sequences", {})
    if sequences:
        lines.append("\n=== Course Sequences ===")
        for seq_name, courses in sequences.items():
            lines.append(f"{seq_name.replace('_', ' ').title()}: {', '.join(courses)}")

    return "\n".join(lines[:60])  # Limit to first 40 courses


def build_chatbot():
    retriever = load_retriever()
    llm = ChatOllama(model="qwen3:0.6b", temperature=0)

    prompt = ChatPromptTemplate.from_template("""
You are a helpful assistant for the University of Alberta Math & Statistics department.
Answer questions based on the context provided.

IMPORTANT TERMINOLOGY CLARIFICATION:
- "Undergraduate" in this context refers to COURSE LEVEL (100-400 level), NOT first-year students
- "Graduate" refers to 500+ level courses
- Course numbers indicate year level: 100-level = Year 1, 200-level = Year 2, etc.
- "Fall/Winter" refers to SEMESTER (Fall term, Winter term), NOT years in a program
- When users ask about "first year courses", look for 100-level courses
- When users ask about "second year courses", look for 200-level courses

Course Dependency Information (use this when users ask about course prerequisites):
{course_graph}

Main Context:
{context}

Question:
{question}

Answer:
""")

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    def build_input(question):
        # Normalize query for case-insensitive matching
        normalized_q = normalize_query(question)

        docs = retriever.invoke(normalized_q)
        context = "\n\n".join(doc.page_content for doc in docs)
        course_info = format_course_graph()
        return {
            "context": context,
            "course_graph": course_info,
            "question": normalized_q,
        }, docs

    def run_chain(question):
        # Normalize query for consistent processing
        normalized_q = normalize_query(question)

        inputs, docs = build_input(normalized_q)
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
