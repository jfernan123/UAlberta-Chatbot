#!/usr/bin/env python
"""
course_graph.py - Build course dependency graph from scraped data

Parses course pages to extract prerequisite relationships.

Usage:
    python course_graph.py                    # Build from data/pages_math.json
    python course_graph.py --input custom.json  # Custom input
    python course_graph.py --output graph.json # Custom output
    python course_graph.py --query "MATH 117"  # Query specific course
    python course_graph.py --list             # List all courses
"""

import json
import re
import argparse
from collections import defaultdict

# Entry-level courses (no prerequisites needed)
ENTRY_LEVEL_COURSES = {
    "MATH 100",
    "MATH 117",
    "MATH 134",
    "MATH 144",
    "MATH 154",
    "MATH 102",
    "MATH 125",
    "MATH 127",
    "STAT 161",
}

# Course sequences - defines which courses are in the same progression
# Note: MATH 102 is taken concurrently with MATH 101/209 (not after), so it's separate
# Note: MATH 127 is taken concurrently with MATH 118/217 (not after), so it's separate
COURSE_SEQUENCES = {
    "engineering": [
        "MATH 100",
        "MATH 101",
        "MATH 209",
    ],  # Linear Algebra (MATH 102) is concurrent
    "honors": [
        "MATH 117",
        "MATH 118",
        "MATH 217",
    ],  # Linear Algebra (MATH 127) is concurrent
    "regular_life_sci": ["MATH 134", "MATH 136"],
    "regular_math_phys": ["MATH 144", "MATH 146"],
    "regular_business": ["MATH 154", "MATH 156"],
    "regular_linear_alg": ["MATH 125"],
    "analysis": ["MATH 216"],
}

# Build lookup: course -> sequence name
COURSE_TO_SEQUENCE = {}
for seq_name, courses in COURSE_SEQUENCES.items():
    for course in courses:
        COURSE_TO_SEQUENCE[course] = seq_name


def extract_course_code(text):
    """Extract course code (e.g., MATH 101) from text."""
    pattern = r"\b(MATH|STAT)\s*(\d{3})\b"
    matches = re.findall(pattern, text, re.IGNORECASE)
    return list(set([f"{prefix.upper()} {num}" for prefix, num in matches]))


def is_entry_level(course_code):
    """Check if course is entry-level (no prerequisites)."""
    return course_code in ENTRY_LEVEL_COURSES


def get_sequence(course_code):
    """Get the sequence a course belongs to."""
    return COURSE_TO_SEQUENCE.get(course_code)


def same_sequence(c1, c2):
    """Check if two courses are in the same sequence."""
    seq1 = get_sequence(c1)
    seq2 = get_sequence(c2)
    if seq1 is None or seq2 is None:
        return False
    return seq1 == seq2


def extract_courses_from_program_pages(data):
    """Extract course information from program pages (not just calendar course pages)."""
    courses = {}

    for page in data:
        url = page.get("url", "")

        # Skip if it's already a calendar course page (we handle those separately)
        if "preview_course" in url:
            continue

        # Process all sections
        for section in page.get("sections", []):
            content = section.get("content", "")
            heading = section.get("heading", "")

            # Extract all course codes mentioned
            course_codes = extract_course_code(content)

            for course_code in course_codes:
                # Skip if we already have this course with better info
                if course_code in courses:
                    continue

                # Determine year level from course number
                try:
                    course_num = int(course_code.split()[1])
                    if 100 <= course_num < 200:
                        year_level = 1
                    elif 200 <= course_num < 300:
                        year_level = 2
                    elif 300 <= course_num < 400:
                        year_level = 3
                    elif 400 <= course_num < 500:
                        year_level = 4
                    elif 500 <= course_num < 600:
                        year_level = 5  # Graduate
                    else:
                        year_level = 0
                except:
                    year_level = 0

                # Store basic info (name will be updated if we find better info)
                courses[course_code] = {
                    "name": f"Course {course_code}",
                    "url": url,
                    "year_level": year_level,
                    "alternatives": [],
                    "source": "program_page",
                }

    return courses


def parse_course_prerequisites(content, primary_course_code):
    """Extract prerequisites from course content."""
    # Get the primary course this page is about
    primary = primary_course_code

    # Find all course codes in the content
    all_courses = extract_course_code(content)

    # Remove the primary course from prerequisites
    potential_prereqs = [c for c in all_courses if c != primary]

    # Look for prerequisite section specifically
    prereqs = []

    # Split content into sections
    lines = content.split("\n")
    in_prereq_section = False

    for line in lines:
        line_lower = line.lower()

        # Check if we're entering a prerequisite section
        if "prereq" in line_lower or "require" in line_lower:
            in_prereq_section = True
            continue

        # If we're in prereq section, look for course codes
        if in_prereq_section:
            # Stop at a new section heading (all caps or specific keywords)
            if line.strip() and (
                line.strip().isupper() or "note" in line_lower or "coreq" in line_lower
            ):
                in_prereq_section = False
                continue

            # Extract course codes from this line
            codes = extract_course_code(line)
            prereqs.extend(codes)

    # If no explicit prereq section found, use the last courses mentioned (they're often prereqs)
    if not prereqs and len(potential_prereqs) > 1:
        prereqs = potential_prereqs[1:4]  # Skip first (it's the course itself)

    # Filter out high school math (30, 31, etc.)
    prereqs = [p for p in prereqs if len(p.split()[1]) == 3]

    return list(set(prereqs))[:4]  # Max 4 prereqs


def extract_course_name(content):
    """Extract course name from content."""
    # Pattern: "MATH 100 - Course Name"
    match = re.search(r"(MATH|STAT)\s*(\d+)\s*-\s*([A-Za-z][^-]+)", content)
    if match:
        return match.group(3).strip()[:60]
    return "Unknown"


def extract_course_code_from_url(url):
    """Extract course code from URL or content."""
    # Try to find course code in URL
    # URL pattern: preview_course_nopop.php?catoid=56&coid=XXXXX
    # We need to parse the actual content
    return None


def extract_primary_course(content):
    """Extract the primary course code and name from the very start of content."""
    # Get content before pipe (that's the main course info)
    main_content = content.split("|")[0] if "|" in content else content[:150]

    # Pattern: "MATH 100 - Course Name -" (trailing dash is OK)
    match = re.match(r"^(MATH|STAT)\s*(\d+)\s*-\s*(.+?)\s*-", main_content.strip())
    if match:
        prefix = match.group(1)
        num = match.group(2)
        name = match.group(3).strip()
        return f"{prefix} {num}", name[:50]

    return None, "Unknown Course"


def extract_course_name_simple(content):
    """Extract course name - wrapper for backward compatibility."""
    code, name = extract_primary_course(content)
    return name if name != "Unknown Course" else "Unknown Course"


def extract_course_dependencies(content, course_code):
    """
    Extract raw dependencies from course page content.
    Returns (prerequisites, next_courses) from the pipe-separated content.

    Pattern:
    - Part 2: Sometimes has actual prerequisite (especially for Year 2+ courses)
    - Part 3+: Next courses (what you take after this course)
    - Avoid contextual mentions like "may be admitted", "consent", "equivalent"
    """
    parts = content.split("|")

    prereqs = []
    next_courses = []

    # Contextual keywords that indicate exceptions, not actual dependencies
    skip_patterns = [
        "may be admitted",
        "consent",
        "equivalent",
        "corequisite",
        "recommended",
    ]

    def is_contextual(text):
        """Check if text contains contextual mentions (exceptions, not prereqs)."""
        text_lower = text.lower()
        return any(pattern in text_lower for pattern in skip_patterns)

    # Part 2: Check for actual prerequisites (especially for non-entry courses)
    if len(parts) > 2:
        part2 = parts[2]
        codes_p2 = extract_course_code(part2)
        # If Part 2 is short and has a single course code, it's likely a prereq
        if len(codes_p2) == 1 and len(part2) < 200 and not is_contextual(part2):
            prereqs.extend(codes_p2)
        elif "prerequisite" in part2.lower() and not is_contextual(part2):
            prereqs.extend([c for c in codes_p2 if c != course_code])

    # Part 3+: Next courses (what you take after this course)
    if len(parts) > 3:
        for part in parts[3:]:
            # Skip contextual mentions
            if is_contextual(part):
                continue
            codes = extract_course_code(part)
            for c in codes:
                if c != course_code and len(c.split()[1]) == 3:
                    next_courses.append(c)

    # If Part 2 has multiple course codes or mentions alternatives, it's entry alternatives
    if len(parts) > 2:
        part2 = parts[2]
        codes_p2 = extract_course_code(part2)
        if len(codes_p2) > 1 or " or " in part2.lower():
            prereqs = []  # Clear prereqs from Part 2

    return list(set(prereqs)), list(set(next_courses))


def forward_pass(data):
    """
    Forward pass: Extract raw prereqs and next_courses from course pages.
    Returns dict: {course_code: {"prereqs": [...], "next_courses": [...], "entry_alts": [...]}}
    """
    course_data = {}

    for page in data:
        if "preview_course" not in page.get("url", ""):
            continue

        for section in page.get("sections", []):
            content = section["content"]
            parts = content.split("|")
            if len(parts) < 3:
                continue

            # Extract primary course from start
            course_code, course_name = extract_primary_course(content)
            if not course_code or len(course_code.split()[1]) != 3:
                continue

            prereqs, next_courses = extract_course_dependencies(content, course_code)

            # Entry alternatives: courses from Part 2 that are entry-level (different sequence)
            entry_alts = []
            if len(parts) > 2:
                part2 = parts[2]
                codes_p2 = extract_course_code(part2)
                if len(codes_p2) > 1 or " or " in part2.lower():
                    entry_alts = [
                        c for c in codes_p2 if c != course_code and is_entry_level(c)
                    ]

            course_data[course_code] = {
                "prereqs": prereqs,
                "next_courses": next_courses,
                "entry_alts": entry_alts,
                "name": course_name,
                "url": page.get("url", ""),
            }

    return course_data


def backward_pass(course_data):
    """
    Backward pass: Reconcile dependencies to filter out cross-sequence dependencies.

    Rules:
    1. Entry-level courses have no prerequisites
    2. If prereq is entry-level course in different sequence -> it's entry alternative, not prereq
    3. Only keep same-sequence prerequisites
    """
    reconciled = {}

    for course_code, data in course_data.items():
        # If course is entry-level, it has no prerequisites
        if is_entry_level(course_code):
            reconciled[course_code] = {
                "name": data["name"],
                "url": data["url"],
                "prerequisites": [],
                "sequence": get_sequence(course_code),
                "alternatives": data["entry_alts"],
            }
            continue

        # Filter prerequisites: only keep same-sequence ones
        filtered_prereqs = []
        for prereq in data["prereqs"]:
            # Skip self-reference
            if prereq == course_code:
                continue
            # Skip entry-level courses that are in DIFFERENT sequences
            if is_entry_level(prereq) and not same_sequence(course_code, prereq):
                continue
            # Keep same-sequence courses or non-entry-level courses
            filtered_prereqs.append(prereq)

        # Determine sequence from entry-level alternatives or first prereq
        sequence = get_sequence(course_code)
        if not sequence:
            for entry in data["entry_alts"]:
                if is_entry_level(entry):
                    sequence = get_sequence(entry)
                    break
            if not sequence:
                for prereq in filtered_prereqs:
                    sequence = get_sequence(prereq)
                    if sequence:
                        break

        reconciled[course_code] = {
            "name": data["name"],
            "url": data["url"],
            "prerequisites": list(set(filtered_prereqs)),
            "sequence": sequence,
            "alternatives": data["entry_alts"],
        }

    return reconciled


def build_dependency_graph(forward_data):
    """
    Build the prerequisite dependency graph.

    Combines:
    1. Raw prerequisites from course pages
    2. Inferred prerequisites from sequences (fills gaps)
    3. Special handling for courses with complex prerequisites
    """
    # First, get all next_course relationships from raw data
    next_course_map = {}
    for course_code, data in forward_data.items():
        for next_course in data["next_courses"]:
            if next_course not in next_course_map:
                next_course_map[next_course] = []
            next_course_map[next_course].append(course_code)

    # Build prerequisites from raw data
    raw_prerequisites = {}
    for course_code in forward_data.keys():
        prereqs = []
        if course_code in next_course_map:
            for prev_course in next_course_map[course_code]:
                if same_sequence(course_code, prev_course):
                    prereqs.append(prev_course)
        raw_prerequisites[course_code] = list(set(prereqs))

    # Second pass: Infer missing prerequisites from sequences
    inferred_prerequisites = {}

    for seq_name, sequence in COURSE_SEQUENCES.items():
        for i, course_code in enumerate(sequence):
            if i == 0:
                inferred_prerequisites[course_code] = []
            else:
                prev_course = None
                for j in range(i - 1, -1, -1):
                    if sequence[j] in forward_data:
                        prev_course = sequence[j]
                        break

                if prev_course:
                    if course_code not in inferred_prerequisites:
                        inferred_prerequisites[course_code] = []
                    if prev_course not in inferred_prerequisites[course_code]:
                        inferred_prerequisites[course_code].append(prev_course)

    # Merge: raw data takes priority, add inferred if missing
    final_prerequisites = {}

    for course_code in forward_data.keys():
        raw_prereqs = raw_prerequisites.get(course_code, [])
        inferred_prereqs = inferred_prerequisites.get(course_code, [])

        combined = list(raw_prereqs)
        for prereq in inferred_prereqs:
            if prereq not in combined:
                combined.append(prereq)

        final_prerequisites[course_code] = combined

    # Special case: MATH 216 has flexible entry (corequisite, not prerequisite)
    if "MATH 216" in final_prerequisites:
        final_prerequisites["MATH 216"] = []

    return final_prerequisites


def build_graph(input_file, output_file):
    """Build course dependency graph from scraped data."""

    print(f"Loading data from {input_file}...")

    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("Running forward pass (extracting raw dependencies)...")
    forward_data = forward_pass(data)
    print(f"  Found {len(forward_data)} courses with structured data")

    print("Running backward pass (reconciling cross-sequence dependencies)...")
    reconciled = backward_pass(forward_data)

    print("Building dependency graph...")
    prerequisites = build_dependency_graph(forward_data)

    # Merge with program page courses and add prerequisites
    program_courses = extract_courses_from_program_pages(data)
    print(f"Found {len(program_courses)} courses from program pages")

    # Combine all courses
    courses = {}

    # First, add reconciled data with prerequisites
    for course_code, data in reconciled.items():
        year_level = 1
        try:
            num = int(course_code.split()[1])
            if 100 <= num < 200:
                year_level = 1
            elif 200 <= num < 300:
                year_level = 2
            elif 300 <= num < 400:
                year_level = 3
            elif 400 <= num < 500:
                year_level = 4
        except:
            pass

        courses[course_code] = {
            "name": data["name"],
            "url": data["url"],
            "year_level": year_level,
            "prerequisites": prerequisites.get(course_code, []),
            "alternatives": data["alternatives"],
            "sequence": data["sequence"],
        }

    # Add program page courses that aren't in calendar data
    for code, info in program_courses.items():
        if code not in courses:
            courses[code] = {
                "name": info["name"],
                "url": info["url"],
                "year_level": info["year_level"],
                "prerequisites": [],
                "alternatives": [],
                "sequence": get_sequence(code),
            }

    # Build dependencies dict
    dependencies = {}
    for course_code, course_info in courses.items():
        if course_info["prerequisites"]:
            dependencies[course_code] = course_info["prerequisites"]

    # Create output structure
    graph = {
        "courses": courses,
        "dependencies": dependencies,
        "sequences": COURSE_SEQUENCES,
        "stats": {
            "total_courses": len(courses),
            "total_dependencies": sum(len(v) for v in dependencies.values()),
        },
    }

    # Save to file
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(graph, f, indent=2)

    print(f"\nCourse Dependency Graph Built!")
    print(f"  Total courses: {graph['stats']['total_courses']}")
    print(f"  Total dependencies: {graph['stats']['total_dependencies']}")
    print(f"  Saved to: {output_file}")

    # Print sample with prerequisites
    print("\n--- Sample Courses with Prerequisites ---")
    sample_courses = [
        "MATH 100",
        "MATH 101",
        "MATH 117",
        "MATH 118",
        "MATH 216",
        "MATH 214",
    ]
    for code in sample_courses:
        if code in courses:
            info = courses[code]
            prereqs = info.get("prerequisites", [])
            print(f"  {code}: {info['name'][:35]}")
            if prereqs:
                print(f"    Prerequisites: {', '.join(prereqs)}")

    return graph


def query_graph(graph_file, course_code=None):
    """Query the course graph."""
    with open(graph_file, "r") as f:
        graph = json.load(f)

    if course_code:
        # Query specific course
        course = graph["courses"].get(course_code)
        if course:
            print(f"\n{course_code}: {course['name']}")
            print(f"  Prerequisites: {course.get('prerequisites', [])}")

            # Find what depends on this course
            dependents = []
            for code, prereqs in graph["dependencies"].items():
                if course_code in prereqs:
                    dependents.append(code)
            if dependents:
                print(f"  Required by: {', '.join(dependents)}")
        else:
            print(f"Course {course_code} not found")
    else:
        # List all courses
        print(f"\nAll courses ({len(graph['courses'])}):")
        for code, info in graph["courses"].items():
            prereqs = info.get("prerequisites", [])
            prereq_str = f" <- {', '.join(prereqs)}" if prereqs else ""
            print(f"  {code}: {info['name'][:30]}{prereq_str}")


def main():
    parser = argparse.ArgumentParser(description="Build course dependency graph")
    parser.add_argument(
        "--input",
        "-i",
        default="data/pages_math.json",
        help="Input JSON file with course data",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="data/course_graph.json",
        help="Output JSON file for graph",
    )
    parser.add_argument(
        "--query", "-q", help="Query a specific course code (e.g., MATH 209)"
    )
    parser.add_argument(
        "--list", "-l", action="store_true", help="List all courses in graph"
    )

    args = parser.parse_args()

    if args.query or args.list:
        # Query mode
        if args.list:
            query_graph(args.output, None)
        else:
            query_graph(args.output, args.query)
    else:
        # Build mode
        build_graph(args.input, args.output)


if __name__ == "__main__":
    main()
