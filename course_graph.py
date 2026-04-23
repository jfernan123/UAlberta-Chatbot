#!/usr/bin/env python
"""
course_graph.py - Build course dependency graph from scraped data

Parses course pages to extract prerequisite relationships.

Usage:
    python course_graph.py                    # Build from data/pages_math.json
    python course_graph.py --input custom.json  # Custom input
    python course_graph.py --output graph.json # Custom output
"""

import json
import re
import argparse
from collections import defaultdict


def extract_course_code(text):
    """Extract course code (e.g., MATH 101) from text."""
    pattern = r"\b(MATH|STAT)\s*(\d{3})\b"
    matches = re.findall(pattern, text, re.IGNORECASE)
    return list(set([f"{prefix.upper()} {num}" for prefix, num in matches]))


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


def build_graph(input_file, output_file):
    """Build course dependency graph from scraped data."""

    print(f"Loading data from {input_file}...")

    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Course info storage
    courses = {}
    dependencies = defaultdict(list)

    # Process each page
    course_pages = [p for p in data if "preview_course" in p.get("url", "")]
    print(f"Found {len(course_pages)} course pages")

    for page in course_pages:
        url = page.get("url", "")

        # Find course requirements section
        for section in page.get("sections", []):
            heading = section.get("heading", "")
            content = section.get("content", "")

            if "course requirements" not in heading.lower():
                continue

            # Extract primary course code and name from start of content
            course_code, course_name = extract_primary_course(content)
            if not course_code:
                continue

            # Skip non-university courses (2-digit numbers)
            try:
                course_num = int(course_code.split()[1])
                if course_num < 100:
                    continue
            except:
                continue

            # Find potential course sequences
            # The data format is: course - alternatives (not true prereqs)
            # We'll note alternatives and mark as "may_take_after"
            prereqs = []

            # Look for the pipe separator - content after it lists alternatives
            if "|" in content:
                alt_part = content.split("|")[1] if len(content.split("|")) > 1 else ""
                alt_codes = extract_course_code(alt_part)
                # Filter to get potential next-level courses
                prereqs = [
                    p for p in alt_codes if p != course_code and len(p.split()[1]) == 3
                ]

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
                else:
                    year_level = 0
            except:
                year_level = 0

            # Store course info
            courses[course_code] = {
                "name": course_name,
                "url": url,
                "year_level": year_level,
                "alternatives": prereqs[
                    :5
                ],  # Note: these are alternatives, not prerequisites
            }

            # Build dependency edges (alternatives)
            for prereq in prereqs:
                if prereq != course_code:
                    dependencies[course_code].append(prereq)

    # Also extract courses from program pages (not just calendar course pages)
    program_courses = extract_courses_from_program_pages(data)
    print(f"Found {len(program_courses)} courses from program pages")

    # Merge program courses with calendar courses (calendar takes priority)
    for code, info in program_courses.items():
        if code not in courses:
            courses[code] = info

    # Create output structure
    graph = {
        "courses": courses,
        "dependencies": dict(dependencies),
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

    # Print sample
    print("\n--- Sample Courses ---")
    for code, info in list(courses.items())[:5]:
        prereqs = info.get("prerequisites", [])
        print(f"  {code}: {info['name'][:40]}")
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
