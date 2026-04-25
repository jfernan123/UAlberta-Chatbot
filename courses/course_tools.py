from langchain.tools import tool
from typing import Optional
import json
import re


def load_course_graph():
    """Load course dependency graph."""
    with open("data/course_graph.json") as f:
        return json.load(f)


def _load_calendar_pages():
    with open("data/pages_calendar.json", encoding="utf-8") as f:
        return json.load(f)


def year_level_label(year):
    """Convert year level number to label."""
    labels = {
        0: "Graduate/Other",
        1: "Year 1",
        2: "Year 2",
        3: "Year 3",
        4: "Year 4",
    }
    return labels.get(year, f"Year {year}")


@tool
def get_stat_courses(year: Optional[int] = None, detail: bool = False) -> str:
    """Get STAT (Statistics) courses, optionally filtered by year level.

    Args:
        year: Optional year level (1-4). If None, returns all STAT courses.
              Year 1 = 100-level courses, Year 2 = 200-level, etc.
        detail: If False (default), returns overview mode - just codes per year.
               If True, returns full details with prerequisites.

    Returns:
        Formatted list of STAT courses.
    """
    graph = load_course_graph()
    stat_courses = {
        code: info for code, info in graph["courses"].items() if code.startswith("STAT")
    }

    if year:
        stat_courses = {
            code: info
            for code, info in stat_courses.items()
            if info.get("year_level") == year
        }

    if not stat_courses:
        return "No STAT courses found for the specified year."

    # Overview mode: list courses by year without full prereq details to avoid verbose output
    if not detail and len(stat_courses) > 10:
        lines = ["STAT Courses (overview):"]
        by_year = {}
        for code, info in stat_courses.items():
            yr = info.get("year_level", 0)
            if yr not in by_year:
                by_year[yr] = []
            by_year[yr].append(code)

        for yr in sorted(by_year.keys()):
            codes = ", ".join(sorted(by_year[yr]))
            lines.append(f"{year_level_label(yr)}: {codes}")

        return "\n".join(lines)

    # Detailed mode: full info with prereqs
    lines = ["STAT Courses:"]

    # Group by year
    by_year = {}
    for code, info in stat_courses.items():
        yr = info.get("year_level", 0)
        if yr not in by_year:
            by_year[yr] = []
        by_year[yr].append((code, info))

    for yr in sorted(by_year.keys()):
        lines.append(f"\n{year_level_label(yr)}:")
        for code, info in sorted(by_year[yr]):
            prereqs = info.get("prerequisites", [])
            math_prereqs = info.get("math_prerequisites", {})

            lines.append(f"  {code}: {info['name']}")

            if prereqs:
                lines.append(f"    Prerequisites: {', '.join(prereqs)}")

            if math_prereqs:
                coreq = math_prereqs.get("coreq", [])
                prereq = math_prereqs.get("prereq", [])
                if coreq:
                    lines.append(f"    MATH Corequisites: {', '.join(coreq)}")
                if prereq:
                    lines.append(f"    MATH Prerequisites: {', '.join(prereq)}")

    return "\n".join(lines)


@tool
def get_math_courses(year: Optional[int] = None, detail: bool = False) -> str:
    """Get MATH (Mathematics) courses, optionally filtered by year level.

    Args:
        year: Optional year level (1-4). If None, returns all MATH courses.
              Year 1 = 100-level courses, Year 2 = 200-level, etc.
        detail: If False (default), returns overview mode - just codes per year.
               If True, returns full details with prerequisites.

    Returns:
        Formatted list of MATH courses.
    """
    graph = load_course_graph()
    math_courses = {
        code: info for code, info in graph["courses"].items() if code.startswith("MATH")
    }

    if year:
        math_courses = {
            code: info
            for code, info in math_courses.items()
            if info.get("year_level") == year
        }

    if not math_courses:
        return "No MATH courses found for the specified year."

    # Overview mode: list courses by year without full prereq details
    if not detail and len(math_courses) > 10:
        lines = ["MATH Courses (overview):"]
        by_year = {}
        for code, info in math_courses.items():
            yr = info.get("year_level", 0)
            if yr not in by_year:
                by_year[yr] = []
            by_year[yr].append(code)

        for yr in sorted(by_year.keys()):
            codes = ", ".join(sorted(by_year[yr]))
            lines.append(f"{year_level_label(yr)}: {codes}")

        return "\n".join(lines)

    # Detailed mode: full info with prereqs
    lines = ["MATH Courses:"]

    # Group by year
    by_year = {}
    for code, info in math_courses.items():
        yr = info.get("year_level", 0)
        if yr not in by_year:
            by_year[yr] = []
        by_year[yr].append((code, info))

    for yr in sorted(by_year.keys()):
        lines.append(f"\n{year_level_label(yr)}:")
        for code, info in sorted(by_year[yr]):
            prereqs = info.get("prerequisites", [])
            seq = info.get("sequence", "")

            lines.append(f"  {code}: {info['name']}")

            if prereqs:
                lines.append(f"    Prerequisites: {', '.join(prereqs)}")

            if seq:
                seq_display = seq.replace("_", " ").title()
                lines.append(f"    Stream: {seq_display}")

    return "\n".join(lines)


@tool
def get_course_prerequisites(course_code: str) -> str:
    """Get prerequisites for a specific course.

    Args:
        course_code: Course code like 'MATH 101' or 'STAT 252'

    Returns:
        Prerequisites and corequisites for the specified course.
    """
    graph = load_course_graph()
    courses = graph.get("courses", {})

    # Try exact match first
    course = courses.get(course_code)

    # Try without spaces
    if not course:
        course_code_nospace = course_code.replace(" ", "")
        for code, info in courses.items():
            if code.replace(" ", "") == course_code_nospace:
                course = info
                course_code = code
                break

    if not course:
        return f"Course '{course_code}' not found in the course database."

    lines = [f"{course_code}: {course['name']}"]
    lines.append(f"Year Level: {year_level_label(course.get('year_level', 0))}")

    prereqs = course.get("prerequisites", [])
    if prereqs:
        lines.append(f"Prerequisites: {', '.join(prereqs)}")
    else:
        lines.append("Prerequisites: None (entry-level course)")

    math_prereqs = course.get("math_prerequisites", {})
    if math_prereqs:
        if math_prereqs.get("prereq"):
            lines.append(f"MATH Prerequisites: {', '.join(math_prereqs['prereq'])}")
        if math_prereqs.get("coreq"):
            lines.append(f"MATH Corequisites: {', '.join(math_prereqs['coreq'])}")

    return "\n".join(lines)


@tool
def get_course_sequence(sequence_name: str | None = None) -> str:
    """Get courses in a specific sequence or pathway.

    Args:
        sequence_name: Name of the sequence. Options:
            - engineering: Engineering Calculus path
            - honors: Honors Mathematics path
            - regular_life_sci: Life Sciences path
            - regular_math_phys: Math/Physical Sciences path
            - regular_business: Business/Economics path
            - applied_stats: Applied Statistics track
            - probability: Probability track
            - prob_stats_ii: Probability and Statistics II track
            - If None, returns all available sequences

    Returns:
        Courses in the specified sequence with their prerequisites.
    """
    graph = load_course_graph()
    sequences = graph.get("sequences", {})

    if sequence_name is None:
        lines = ["Available Course Sequences:"]
        for name, courses in sequences.items():
            display_name = name.replace("_", " ").title()
            lines.append(f"\n{display_name}:")
            lines.append(f"  {' -> '.join(courses)}")
        return "\n".join(lines)

    courses = sequences.get(sequence_name, [])

    if not courses:
        available = ", ".join(sequences.keys())
        return f"Sequence '{sequence_name}' not found. Available: {available}"

    display_name = sequence_name.replace("_", " ").title()
    lines = [f"{display_name} Sequence:"]
    lines.append(f"  {' -> '.join(courses)}")

    # Add prerequisites for each course
    all_courses = graph.get("courses", {})
    lines.append("\nWith Prerequisites:")
    for code in courses:
        course = all_courses.get(code, {})
        prereqs = course.get("prerequisites", [])
        name = course.get("name", code)
        if prereqs:
            lines.append(f"  {code} ({name}): Prerequisites: {', '.join(prereqs)}")
        else:
            lines.append(f"  {code} ({name}): No prerequisites")

    return "\n".join(lines)


@tool
def search_courses(keyword: str) -> str:
    """Search for courses by keyword in their name.

    Args:
        keyword: Search term (e.g., 'calculus', 'probability', 'regression')

    Returns:
        Matching courses with their details.
    """
    graph = load_course_graph()
    courses = graph.get("courses", {})

    keyword_lower = keyword.lower()
    matches = []

    for code, info in courses.items():
        name = info.get("name", "").lower()
        if keyword_lower in name or keyword_lower in code.lower():
            matches.append((code, info))

    if not matches:
        return f"No courses found matching '{keyword}'."

    lines = [f"Courses matching '{keyword}':"]

    # Overview mode: if >10 courses, just list names (no prereqs to avoid verbose output)
    if len(matches) > 10:
        for code, info in matches[:15]:
            lines.append(f"- {code}: {info['name']}")
        if len(matches) > 15:
            lines.append(f"... and {len(matches) - 15} more courses")
    else:
        # Detailed mode: show prerequisites for each course
        for code, info in matches[:15]:
            prereqs = info.get("prerequisites", [])
            lines.append(f"\n{code}: {info['name']}")
            if prereqs:
                lines.append(f"  Prerequisites: {', '.join(prereqs)}")

    if len(matches) > 15:
        lines.append(f"\n... and {len(matches) - 15} more courses")

    return "\n".join(lines)


@tool
def get_courses_by_level(
    department: Optional[str] = None,
    level: Optional[str] = None,
) -> str:
    """Get courses filtered by department and level (year).

    Args:
        department: "math", "stat", or None for both.
        level: "first" (100s), "second" (200s), "third" (300s),
               "senior" (400s), "graduate" (500+), or "upper" (300+).

    Returns:
        Filtered courses with their names and prerequisites.
    """
    graph = load_course_graph()
    courses = graph.get("courses", {})

    # Normalize level to lowercase for lookup
    level_key = level.lower() if level else None

    # Map level names to course number ranges
    level_ranges = {
        "first": (100, 199),
        "second": (200, 299),
        "third": (300, 399),
        "senior": (400, 499),
        "upper": (300, 999),  # 300+ = upper level undergrad
        "graduate": (500, 999),
    }

    # Determine course number range
    num_range = level_ranges.get(level_key) if level_key else None

    # Filter by department
    if department == "math":
        filtered = {c: info for c, info in courses.items() if c.startswith("MATH")}
    elif department == "stat":
        filtered = {c: info for c, info in courses.items() if c.startswith("STAT")}
    else:
        filtered = courses

    # Filter by level/course number
    if num_range:
        min_num, max_num = num_range
        filtered = {
            c: info
            for c, info in filtered.items()
            if any(
                min_num <= int(c.split()[1]) <= max_num
                for c in [c]
                if c.split()[1].isdigit()
            )
        }

    if not filtered:
        return f"No {department or ''} courses found for level '{level}'."

    # Group by century (100s, 200s, etc.)
    by_century = {}
    for code, info in filtered.items():
        try:
            century = int(code.split()[1]) // 100
            if century not in by_century:
                by_century[century] = []
            by_century[century].append((code, info))
        except Exception:
            pass

    century_labels = {
        1: "First Year (100-level)",
        2: "Second Year (200-level)",
        3: "Third Year (300-level)",
        4: "Senior (400-level)",
        5: "Graduate (500-level)",
    }

    lines = [
        f"{department.title() if department else ''} {level.title() if level else ''} Courses:".strip()
    ]

    total = len(filtered)
    shown = 0
    for century in sorted(by_century.keys()):
        label = century_labels.get(century, f"{century}00-level")
        lines.append(f"\n{label}:")
        for code, info in sorted(by_century[century]):
            prereqs = info.get("prerequisites", [])
            lines.append(f"  {code}: {info['name']}")
            if prereqs:
                lines.append(f"    Prerequisites: {', '.join(prereqs)}")
            shown += 1

    if shown < total:
        lines.append(f"\n... and {total - shown} more courses")

    return "\n".join(lines)


# Known poids for math/stats program pages in the UAlberta calendar
_PROGRAM_POIDS = {
    "honors math":        "84304",
    "honors mathematics": "84304",
    "major math":         "84304",
    "major mathematics":  "84304",
    "minor math":         "84304",
    "minor mathematics":  "84304",
    "honors stat":        "84315",
    "honors statistics":  "84315",
    "major stat":         "84315",
    "major statistics":   "84315",
    "minor stat":         "84315",
    "minor statistics":   "84315",
}


@tool
def get_program_requirements(program: str) -> str:
    """Get the full course requirements for a BSc program (Honors/Major/Minor in Math or Statistics).

    Args:
        program: One of 'honors math', 'major math', 'honors statistics', 'major statistics', etc.

    Returns:
        Full list of required courses with units for the specified program.
    """
    key = program.lower().strip()
    poid = _PROGRAM_POIDS.get(key)

    # Fuzzy match if exact key not found
    if not poid:
        for k, p in _PROGRAM_POIDS.items():
            if all(w in key for w in k.split()):
                poid = p
                break

    if not poid:
        available = ", ".join(sorted(set(_PROGRAM_POIDS.keys())))
        return f"Program '{program}' not recognized. Available: {available}"

    pages = _load_calendar_pages()
    page = next((p for p in pages if f"poid={poid}" in p.get("url", "")), None)
    if not page:
        return f"Program page (poid={poid}) not found in calendar data."

    # Determine which sub-program to extract based on key
    if "minor" in key:
        target_heading = "Minor"
    elif "major" in key:
        target_heading = "Major"
    else:
        target_heading = "Honors"

    # Collect sections relevant to the requested sub-program
    lines = []
    in_section = False
    for s in page.get("sections", []):
        heading = s["heading"].strip()
        content = s["content"].strip()

        # Detect section start
        if f"{target_heading} in" in heading and "Requirements" in heading:
            in_section = True
            lines.append(f"\n{heading}:")
            continue

        # Detect next sub-program section (stop collecting)
        if in_section and any(
            f"{prog} in" in heading and "Requirements" in heading
            for prog in ["Honors", "Major", "Minor"]
            if prog != target_heading
        ):
            break

        if in_section:
            if not content:
                lines.append(f"\n{heading}:")
            elif heading.startswith(("3 units", "6 units")):
                lines.append(f"  Choose {heading} {content}")
            else:
                lines.append(f"{heading}: {content}")

    if not lines:
        return f"Could not find {target_heading} requirements for poid={poid}."

    # Prepend summary line from the overview section
    for s in page.get("sections", []):
        if "Courses for Subject Area Requirements" in s["heading"]:
            summary = s["content"][:300]
            lines.insert(0, summary)
            break

    return "\n".join(lines)
