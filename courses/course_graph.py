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

# Entry-level courses (no prerequisites needed - just high school math)
ENTRY_LEVEL_COURSES = {
    # MATH entry level courses
    "MATH 100",
    "MATH 117",
    "MATH 134",
    "MATH 144",
    "MATH 154",
    "MATH 102",
    "MATH 125",
    "MATH 127",
    # STAT entry level courses (high school math only)
    "STAT 151",
    "STAT 161",
    "STAT 181",
}

# MATH course sequences
MATH_SEQUENCES = {
    "engineering": ["MATH 100", "MATH 101", "MATH 209"],  # STAT 235 after MATH 101
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

# STAT course sequences
STAT_SEQUENCES = {
    "applied_stats": ["STAT 151", "STAT 252", "STAT 337", "STAT 368", "STAT 378"],
    "probability": ["STAT 181", "STAT 265", "STAT 371", "STAT 471"],
    "prob_stats_ii": ["STAT 266", "STAT 276", "STAT 361", "STAT 372", "STAT 378"],
    "engineering_stats": ["STAT 235"],  # After MATH 101 in engineering
}

# Combined sequences
COURSE_SEQUENCES = {**MATH_SEQUENCES, **STAT_SEQUENCES}

# STAT course names (from UAlberta catalogue)
STAT_COURSE_NAMES = {
    "STAT 151": "Introduction to Applied Statistics I",
    "STAT 161": "Introductory Statistics for Business and Economics",
    "STAT 181": "Introduction to Combinatorics and Probability",
    "STAT 235": "Introductory Statistics for Engineering",
    "STAT 252": "Introduction to Applied Statistics II",
    "STAT 265": "Probability and Statistics I",
    "STAT 266": "Probability and Statistics II",
    "STAT 276": "Statistics for Data Science",
    "STAT 281": "Probability by Counting and Queuing",
    "STAT 337": "Biostatistics",
    "STAT 353": "Life Contingencies I",
    "STAT 361": "Sampling Techniques",
    "STAT 368": "Introduction to Design and Analysis of Experiments",
    "STAT 371": "Probability and Stochastic Processes",
    "STAT 372": "Mathematical Statistics",
    "STAT 378": "Applied Regression Analysis",
    "STAT 413": "Computing for Data Science",
    "STAT 432": "Survival Analysis",
    "STAT 437": "Applied Statistical Methods",
    "STAT 441": "Statistical Methods for Learning and Data Mining",
    "STAT 453": "Risk Theory",
    "STAT 471": "Probability I",
    "STAT 479": "Time Series Analysis",
    "STAT 497": "Reading in Statistics",
    "STAT 498": "Statistical Topics in Data Science",
    "STAT 499": "Research Project",
}

# STAT 500-level (graduate) course names
STAT_500_NAMES = {
    "STAT 501": "Directed Study I",
    "STAT 502": "Directed Study II",
    "STAT 503": "Directed Study III",
    "STAT 504": "Directed Study IV",
    "STAT 505": "Directed Study V",
    "STAT 512": "Techniques of Mathematics for Statistics",
    "STAT 513": "Statistical Computing",
    "STAT 514": "Statistics for Clinical Trials I",
    "STAT 515": "Statistics for Clinical Trials II",
    "STAT 532": "Survival Analysis",
    "STAT 537": "Statistical Methods for Applied Research II",
    "STAT 541": "Statistics for Learning",
    "STAT 553": "Risk Theory",
    "STAT 561": "Sample Survey Methodology",
    "STAT 562": "Discrete Data Analysis",
    "STAT 566": "Methods of Statistical Inference",
    "STAT 568": "Design and Analysis of Experiments",
    "STAT 571": "Probability and Measure",
    "STAT 575": "Multivariate Analysis",
    "STAT 578": "Regression Analysis",
    "STAT 580": "Stochastic Processes",
    "STAT 590": "Statistical Consulting",
}

# STAT graduate/thesis courses
STAT_GRADUATE_NAMES = {
    "STAT 600": "Reading in Statistics",
    "STAT 637": "Statistical Methods for Applied Research III",
    "STAT 664": "Advanced Statistical Inference",
    "STAT 665": "Asymptotic Methods in Statistical Inference",
    "STAT 900": "Directed Research Project",
    "STAT 900A": "Directed Research Project",
    "STAT 900B": "Directed Research Project",
    "STAT 901": "Practicum in Statistics I",
    "STAT 902": "Practicum in Statistics II",
    "STAT 903": "Internship in Biostatistics",
}

# MATH 400-level course names (from UAlberta catalogue)
MATH_400_NAMES = {
    "MATH 405": "Stochastic Analysis I",
    "MATH 408": "Computational Finance",
    "MATH 411": "Honors Complex Variables",
    "MATH 412": "Algebraic Number Theory",
    "MATH 414": "Analysis II",
    "MATH 415": "Mathematical Finance I",
    "MATH 417": "Real Analysis",
    "MATH 418": "Linear Analysis",
    "MATH 421": "Combinatorics",
    "MATH 422": "Coding Theory",
    "MATH 424": "Algebra: Groups and Fields",
    "MATH 428": "Advanced Ring Theory",
    "MATH 429": "Advanced Group Theory and Representation Theory",
    "MATH 432": "Intermediate Differential Equations",
    "MATH 436": "Intermediate Partial Differential Equations",
    "MATH 447": "Elementary Topology",
    "MATH 448": "Introduction to Differential Geometry",
    "MATH 467": "Theory of Probability",
    "MATH 471": "Markov Models",
    "MATH 483": "Topics in Algebra",
    "MATH 497": "Reading in Mathematics",
    "MATH 498": "Mathematical Topics in Data Science",
    "MATH 499": "Research Project",
}

# MATH 500-level (graduate) course names
MATH_500_NAMES = {
    "MATH 505": "Stochastic Analysis I",
    "MATH 506": "Complex Variables",
    "MATH 508": "Computational Finance",
    "MATH 509": "Data Structures and Platforms",
    "MATH 510": "Stochastic Analysis II",
    "MATH 512": "Algebraic Number Theory",
    "MATH 514": "Measure Theory I",
    "MATH 515": "Mathematical Finance I",
    "MATH 516": "Linear Analysis",
    "MATH 518": "Functional Analysis",
    "MATH 519": "Introduction to Operator Algebras",
    "MATH 520": "Mathematical Finance II",
    "MATH 521": "Differential Manifolds",
    "MATH 524": "Ordinary Differential Equations IIA",
    "MATH 525": "Ordinary Differential Equations IIB",
    "MATH 527": "Intermediate Partial Differential Equations",
    "MATH 530": "Algebraic Topology",
    "MATH 535": "Numerical Methods I",
    "MATH 536": "Numerical Solutions of Partial Differential Equations I",
    "MATH 538": "Techniques of Applied Mathematics",
    "MATH 539": "Applied Functional Analysis",
    "MATH 542": "Fourier Analysis",
    "MATH 543": "Measure Theory II",
    "MATH 556": "Introduction to Fluid Mechanics",
    "MATH 570": "Mathematical Biology",
    "MATH 572": "Mathematical Modelling in Industry, Government, and Sciences",
    "MATH 574": "Mathematical Modeling of Infectious Diseases",
    "MATH 581": "Group Theory",
    "MATH 582": "Rings and Modules",
    "MATH 583": "Topics in Algebra",
}

# Graduate/thesis courses
MATH_GRADUATE_NAMES = {
    "MATH 600": "Reading in Mathematics",
    "MATH 601": "Graduate Colloquium",
    "MATH 617": "Topics in Functional Analysis I",
    "MATH 623": "Topics in Differential Geometry and Mechanics",
    "MATH 625": "Advanced Mathematical Finance",
    "MATH 653": "Seminar in Functional Analysis",
    "MATH 655": "Topics in Fluid Dynamics",
    "MATH 663": "Topics in Applied Mathematics I",
    "MATH 664": "Topics in Applied Mathematics II",
    "MATH 667": "Topics in Differential Equations I",
    "MATH 676": "Topics in Geometry I",
    "MATH 681": "Topics in Algebra",
    "MATH 682": "Topics in Algebra",
    "MATH 900": "Directed Research Project",
    "MATH 900A": "Directed Research Project",
    "MATH 900B": "Directed Research Project",
}

# MATH 300-level course names (from UAlberta catalogue)
MATH_300_NAMES = {
    "MATH 300": "Advanced Boundary Value Problems",
    "MATH 311": "Introduction to Ring Theory",
    "MATH 315": "Calculus IV",
    "MATH 317": "Honors Calculus IV",
    "MATH 322": "Graph Theory",
    "MATH 325": "Linear Algebra III",
    "MATH 326": "Ring and Modules",
    "MATH 328": "Group Theory",
    "MATH 334": "Introduction to Partial Differential Equations",
    "MATH 336": "Methods of Applied Mathematics",
    "MATH 337": "Applied Linear Algebra",
    "MATH 341": "Geometry of Convex Sets",
    "MATH 343": "Methods of Optimization",
    "MATH 348": "Differential Geometry of Curves and Surfaces",
    "MATH 356": "Introduction to Mathematical Finance II",
    "MATH 357": "Game Theory and Economic Modelling",
    "MATH 371": "Mathematical Programming and Optimization I",
    "MATH 372": "Mathematical Programming and Optimization II",
    "MATH 373": "Continuous Optimization",
    "MATH 381": "Numerical Analysis",
}

# MATH prerequisites (from UAlberta catalogue)
MATH_PREREQUISITES = {
    # 200-level
    "MATH 201": {"coreq": ["MATH 209", "MATH 214"]},
    "MATH 209": {"prereq": ["MATH 101"], "coreq": ["MATH 102"]},
    "MATH 214": {
        "prereq": [
            "MATH 101",
            "MATH 115",
            "MATH 118",
            "MATH 136",
            "MATH 146",
            "MATH 156",
        ]
    },
    "MATH 216": {
        "coreq": ["MATH 101", "MATH 115", "MATH 136", "MATH 146", "MATH 156", "SCI 100"]
    },
    "MATH 217": {
        "prereq": ["MATH 102", "MATH 125", "MATH 127"],
        "coreq": ["MATH 118", "MATH 216"],
    },
    "MATH 225": {
        "prereq": [
            "MATH 100",
            "MATH 113",
            "MATH 114",
            "MATH 117",
            "MATH 134",
            "MATH 144",
            "MATH 154",
            "SCI 100",
        ],
        "coreq": ["MATH 102", "MATH 125", "MATH 127"],
    },
    "MATH 226": {"prereq": ["MATH 125"]},
    "MATH 227": {"prereq": ["MATH 127"], "coreq": ["MATH 226"]},
    "MATH 228": {"prereq": ["MATH 102", "MATH 125", "MATH 127"]},
    "MATH 241": {
        "prereq": [
            "MATH 100",
            "MATH 101",
            "MATH 114",
            "MATH 115",
            "MATH 117",
            "MATH 125",
            "MATH 127",
            "MATH 134",
            "MATH 136",
            "MATH 144",
            "MATH 146",
            "MATH 154",
            "MATH 156",
            "SCI 100",
        ]
    },
    "MATH 243": {"prereq": ["MATH 241"]},
    "MATH 253": {
        "prereq": [
            "MATH 101",
            "MATH 115",
            "MATH 118",
            "MATH 136",
            "MATH 146",
            "MATH 156",
            "SCI 100",
        ],
        "coreq": ["MATH 209", "MATH 214"],
    },
    "MATH 256": {"prereq": ["MATH 125", "MATH 127"]},
    # 300-level
    "MATH 300": {"prereq": ["MATH 201", "MATH 209"]},
    "MATH 309": {"prereq": ["MATH 209"]},
    "MATH 311": {"coreq": ["MATH 215", "MATH 315", "MATH 317", "MA PH 351"]},
    "MATH 314": {"prereq": ["MATH 209", "MATH 215"]},
    "MATH 315": {
        "prereq": ["MATH 102", "MATH 125", "MATH 127"],
        "coreq": ["MATH 214", "MATH 217"],
    },
    "MATH 317": {"prereq": ["MATH 217"]},
    "MATH 322": {"prereq": ["MATH 102", "MATH 125", "MATH 127"]},
    "MATH 324": {"prereq": ["MATH 227", "MATH 228"]},
    "MATH 325": {"prereq": ["MATH 225"]},
    "MATH 326": {"prereq": ["MATH 227"], "coreq": ["MATH 225", "MATH 228"]},
    "MATH 327": {"prereq": ["MATH 226", "MATH 227"]},
    "MATH 328": {"prereq": ["MATH 227", "MATH 228"]},
    "MATH 329": {"prereq": ["MATH 327"]},
    "MATH 334": {
        "prereq": ["MATH 102", "MATH 125", "MATH 127"],
        "coreq": ["MATH 209", "MATH 214", "MATH 217"],
    },
    "MATH 336": {
        "prereq": ["MATH 225", "MATH 227"],
        "coreq": ["MATH 209", "MATH 217", "MATH 314"],
    },
    "MATH 337": {
        "prereq": ["MATH 209", "MATH 215", "MATH 217", "MATH 315"],
        "coreq": ["MATH 201", "MATH 334", "MATH 336", "MA PH 251"],
    },
    "MATH 341": {"prereq": ["MATH 102", "MATH 125", "MATH 127"]},
    "MATH 343": {"prereq": ["MATH 241"]},
    "MATH 348": {
        "prereq": ["MATH 102", "MATH 125", "MATH 127"],
        "coreq": ["MATH 209", "MATH 215", "MATH 217", "MATH 315"],
    },
    "MATH 356": {"prereq": ["MATH 253"], "coreq": ["STAT 265", "STAT 281"]},
    "MATH 357": {"prereq": ["MATH 356"]},
    "MATH 371": {
        "prereq": ["MATH 102", "MATH 125", "MATH 127"],
        "coreq": ["MATH 209", "MATH 214", "MATH 217"],
    },
    "MATH 372": {
        "prereq": ["MATH 102", "MATH 125", "MATH 127"],
        "coreq": ["MATH 209", "MATH 214", "MATH 217"],
    },
    "MATH 373": {
        "prereq": ["MATH 102", "MATH 125", "MATH 127"],
        "coreq": ["MATH 209", "MATH 214", "MATH 217"],
    },
    "MATH 381": {
        "prereq": ["MATH 102", "MATH 125", "MATH 127"],
        "coreq": ["MATH 209", "MATH 214", "MATH 217"],
    },
    # 400-level
    "MATH 405": {"prereq": ["STAT 371", "STAT 281", "MATH 467"]},
    "MATH 408": {"prereq": ["STAT 471"], "coreq": ["ECE 342"]},
    "MATH 411": {"prereq": ["MATH 314", "MATH 317"]},
    "MATH 412": {"prereq": ["MATH 326"]},
    "MATH 414": {"prereq": ["MATH 314"]},
    "MATH 415": {"coreq": ["STAT 471"]},
    "MATH 417": {"prereq": ["MATH 317", "MATH 414"]},
    "MATH 418": {"prereq": ["MATH 417"], "coreq": ["MATH 447"]},
    "MATH 421": {"prereq": ["MATH 326", "MATH 327"]},
    "MATH 422": {"prereq": ["MATH 227"], "coreq": ["MATH 228"]},
    "MATH 424": {"prereq": ["MATH 326", "MATH 228"], "coreq": ["MATH 328"]},
    "MATH 428": {"prereq": ["MATH 326", "MATH 327"]},
    "MATH 429": {"prereq": ["MATH 328", "MATH 327"]},
    "MATH 432": {"prereq": ["MATH 201", "MATH 334", "MATH 336", "MA PH 251"]},
    "MATH 436": {"prereq": ["MATH 300", "MATH 337"]},
    "MATH 447": {
        "prereq": ["MATH 216", "MATH 217"],
        "coreq": ["MATH 328", "MA PH 464"],
    },
    "MATH 448": {"prereq": ["MATH 348"], "coreq": ["MATH 225", "MATH 227"]},
    "MATH 467": {"prereq": ["MATH 214", "MATH 216"], "coreq": ["MATH 217"]},
    "MATH 471": {"prereq": ["STAT 281", "STAT 371"]},
    # 500-level (graduate)
    "MATH 505": {"prereq": ["STAT 371", "STAT 281", "MATH 467"]},
    "MATH 506": {"prereq": ["MATH 411"]},
    "MATH 508": {"prereq": ["STAT 371", "STAT 281", "MATH 467", "FIN 654", "ECON 598"]},
    "MATH 510": {"prereq": ["MATH 505"]},
    "MATH 512": {"prereq": ["MATH 326"]},
    "MATH 514": {"prereq": ["MATH 317"]},
    "MATH 515": {"prereq": ["STAT 471"]},
    "MATH 516": {"prereq": ["MATH 417"], "coreq": ["MATH 447"]},
    "MATH 518": {"prereq": ["MATH 516"], "coreq": ["MATH 447"]},
    "MATH 519": {"prereq": ["MATH 516"], "coreq": ["MATH 447"]},
    "MATH 520": {"prereq": ["MATH 515"], "coreq": ["MATH 510"]},
    "MATH 521": {"prereq": ["MATH 446", "MATH 448"]},
    "MATH 524": {"prereq": ["MATH 334", "MATH 336"]},
    "MATH 525": {"prereq": ["MATH 524"]},
    "MATH 527": {"prereq": ["MATH 436"], "coreq": ["MATH 516"]},
    "MATH 530": {"prereq": ["MATH 227", "MATH 317", "MATH 447"]},
    "MATH 535": {"prereq": []},
    "MATH 536": {"prereq": ["MATH 337", "MATH 436"]},
    "MATH 538": {"prereq": ["MATH 438"]},
    "MATH 539": {"prereq": ["MATH 438"]},
    "MATH 542": {"prereq": ["MATH 418"]},
    "MATH 543": {"prereq": ["MATH 417", "MATH 514"], "coreq": ["MATH 447"]},
    "MATH 556": {"prereq": ["MATH 311", "MATH 411"], "coreq": ["MATH 436"]},
    "MATH 570": {"prereq": ["MATH 524"]},
    "MATH 572": {"prereq": []},
    "MATH 574": {"prereq": ["MATH 334", "MATH 336"]},
    "MATH 581": {"prereq": ["MATH 328"]},
    "MATH 582": {"prereq": ["MATH 326"]},
    "MATH 583": {"prereq": ["MATH 326", "MATH 327", "MATH 328", "MATH 329"]},
}

# MATH prerequisites for STAT courses (cross-discipline)
STAT_MATH_PREREQUISITES = {
    "STAT 181": {
        "prereq": ["MATH 125", "MATH 127"],
        "coreq": ["MATH 101", "MATH 118", "MATH 136", "MATH 146", "MATH 156"],
    },
    "STAT 235": {"prereq": ["MATH 100"], "coreq": ["MATH 101"]},
    "STAT 265": {"coreq": ["MATH 209", "MATH 214", "MATH 217"]},
    "STAT 266": {
        "prereq": ["MATH 209", "MATH 214", "MATH 217"],
        "coreq": ["MATH 225", "MATH 227"],
    },
    "STAT 276": {"coreq": ["MATH 117", "MATH 216"]},
    "STAT 353": {"prereq": ["MATH 253"]},
}

# STAT prerequisites (from UAlberta catalogue)
STAT_PREREQUISITES = {
    # 200-level
    "STAT 252": ["STAT 151", "STAT 161", "STAT 235", "STAT 141", "SCI 151"],
    "STAT 265": [],
    "STAT 266": ["STAT 265", "STAT 281"],
    "STAT 276": ["STAT 265", "STAT 281"],
    "STAT 281": [],
    # 300-level
    "STAT 337": ["STAT 151", "STAT 161", "SCI 151"],
    "STAT 353": ["MATH 253", "STAT 265", "STAT 281"],
    "STAT 361": ["STAT 266", "STAT 276"],
    "STAT 368": ["STAT 266", "STAT 276"],
    "STAT 371": ["STAT 265"],
    "STAT 372": ["STAT 266", "STAT 276"],
    "STAT 378": ["STAT 266", "STAT 276"],
    # 400-level
    "STAT 413": ["STAT 265", "STAT 281"],
    "STAT 432": ["STAT 372", "STAT 378"],
    "STAT 437": ["STAT 252", "STAT 337"],
    "STAT 441": ["STAT 378"],
    "STAT 453": ["STAT 371", "STAT 281"],
    "STAT 471": ["STAT 371", "STAT 281"],
    "STAT 479": ["STAT 372", "STAT 378"],
    "STAT 497": [],
    "STAT 498": [],
    "STAT 499": [],
    # 500-level
    "STAT 501": ["STAT 252", "STAT 337"],
    "STAT 502": ["STAT 252", "STAT 337"],
    "STAT 503": ["STAT 372", "STAT 378"],
    "STAT 504": [],
    "STAT 505": ["STAT 501", "STAT 502"],
    "STAT 512": [],
    "STAT 513": [],
    "STAT 514": [],
    "STAT 515": ["STAT 514"],
    "STAT 532": ["STAT 372"],
    "STAT 537": ["STAT 437"],
    "STAT 541": [],
    "STAT 553": ["STAT 371"],
    "STAT 561": ["STAT 361", "STAT 372", "STAT 471"],
    "STAT 562": ["STAT 372", "STAT 471"],
    "STAT 566": ["STAT 471"],
    "STAT 568": ["STAT 368"],
    "STAT 571": ["STAT 471"],
    "STAT 575": ["STAT 372", "STAT 512"],
    "STAT 578": ["STAT 378"],
    "STAT 580": ["STAT 471"],
    "STAT 590": ["STAT 568", "STAT 578"],
    # Graduate
    "STAT 600": [],
    "STAT 637": ["STAT 537"],
    "STAT 664": ["STAT 512", "STAT 566"],
    "STAT 665": ["STAT 566", "STAT 512"],
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

    # Add STAT prerequisites from our STAT_PREREQUISITES mapping
    for stat_course, prereqs in STAT_PREREQUISITES.items():
        if stat_course not in final_prerequisites:
            final_prerequisites[stat_course] = []
        # Add any STAT prerequisites not already present
        for prereq in prereqs:
            if prereq not in final_prerequisites[stat_course]:
                final_prerequisites[stat_course].append(prereq)

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
            year_level = info["year_level"]
            # Use known STAT names if available
            name = STAT_COURSE_NAMES.get(code, info["name"])

            # Get STAT prerequisites
            stat_prereqs = STAT_PREREQUISITES.get(code, [])
            math_prereqs = STAT_MATH_PREREQUISITES.get(code, {})

            courses[code] = {
                "name": name,
                "url": info["url"],
                "year_level": year_level,
                "prerequisites": stat_prereqs,
                "alternatives": [],
                "sequence": get_sequence(code),
                "math_prerequisites": math_prereqs if math_prereqs else None,
            }

    # Add any remaining STAT courses from our STAT_COURSE_NAMES that aren't in courses yet
    for stat_code, stat_name in STAT_COURSE_NAMES.items():
        if stat_code not in courses:
            try:
                year_level = int(stat_code.split()[1])
                if 100 <= year_level < 200:
                    year_level = 1
                elif 200 <= year_level < 300:
                    year_level = 2
                elif 300 <= year_level < 400:
                    year_level = 3
                elif 400 <= year_level < 500:
                    year_level = 4
                else:
                    year_level = 5
            except:
                year_level = 1

            stat_prereqs = STAT_PREREQUISITES.get(stat_code, [])
            math_prereqs = STAT_MATH_PREREQUISITES.get(stat_code, {})

            courses[stat_code] = {
                "name": stat_name,
                "url": "",
                "year_level": year_level,
                "prerequisites": stat_prereqs,
                "alternatives": [],
                "sequence": get_sequence(stat_code),
                "math_prerequisites": math_prereqs if math_prereqs else None,
            }

    # Add STAT 500-level course names
    for stat_code, stat_name in STAT_500_NAMES.items():
        if stat_code in courses:
            courses[stat_code]["name"] = stat_name
        else:
            try:
                year_level = int(stat_code.split()[1])
                if 500 <= year_level < 600:
                    year_level = 5
            except:
                year_level = 5

            prereqs = STAT_PREREQUISITES.get(stat_code, [])

            courses[stat_code] = {
                "name": stat_name,
                "url": "",
                "year_level": year_level,
                "prerequisites": prereqs,
                "alternatives": [],
                "sequence": get_sequence(stat_code),
            }

    # Add STAT graduate courses
    for stat_code, stat_name in STAT_GRADUATE_NAMES.items():
        if stat_code in courses:
            courses[stat_code]["name"] = stat_name
        else:
            try:
                year_level = int(stat_code.split()[1])
                if year_level >= 600:
                    year_level = 5
            except:
                year_level = 5

            prereqs = STAT_PREREQUISITES.get(stat_code, [])

            courses[stat_code] = {
                "name": stat_name,
                "url": "",
                "year_level": year_level,
                "prerequisites": prereqs,
                "alternatives": [],
                "sequence": get_sequence(stat_code),
            }

    # Add MATH 300-level course names
    for math_code, math_name in MATH_300_NAMES.items():
        if math_code in courses:
            courses[math_code]["name"] = math_name
        else:
            try:
                year_level = int(math_code.split()[1])
                if 300 <= year_level < 400:
                    year_level = 3
            except:
                year_level = 3

            courses[math_code] = {
                "name": math_name,
                "url": "",
                "year_level": year_level,
                "prerequisites": [],
                "alternatives": [],
                "sequence": get_sequence(math_code),
            }

    # Add MATH 400-level course names
    for math_code, math_name in MATH_400_NAMES.items():
        if math_code in courses:
            courses[math_code]["name"] = math_name
        else:
            try:
                year_level = int(math_code.split()[1])
                if 400 <= year_level < 500:
                    year_level = 4
            except:
                year_level = 4

            prereq_data = MATH_PREREQUISITES.get(math_code, {})
            prereqs = prereq_data.get("prereq", [])

            courses[math_code] = {
                "name": math_name,
                "url": "",
                "year_level": year_level,
                "prerequisites": prereqs,
                "alternatives": [],
                "sequence": get_sequence(math_code),
            }

    # Add MATH 500-level course names
    for math_code, math_name in MATH_500_NAMES.items():
        if math_code in courses:
            courses[math_code]["name"] = math_name
        else:
            try:
                year_level = int(math_code.split()[1])
                if 500 <= year_level < 600:
                    year_level = 5
            except:
                year_level = 5

            prereq_data = MATH_PREREQUISITES.get(math_code, {})
            prereqs = prereq_data.get("prereq", [])

            courses[math_code] = {
                "name": math_name,
                "url": "",
                "year_level": year_level,
                "prerequisites": prereqs,
                "alternatives": [],
                "sequence": get_sequence(math_code),
            }

    # Add graduate courses
    for math_code, math_name in MATH_GRADUATE_NAMES.items():
        if math_code in courses:
            courses[math_code]["name"] = math_name
        else:
            try:
                year_level = int(math_code.split()[1])
                if year_level >= 600:
                    year_level = 5
            except:
                year_level = 5

            prereq_data = MATH_PREREQUISITES.get(math_code, {})
            prereqs = prereq_data.get("prereq", [])

            courses[math_code] = {
                "name": math_name,
                "url": "",
                "year_level": year_level,
                "prerequisites": prereqs,
                "alternatives": [],
                "sequence": get_sequence(math_code),
            }

    # Also update 200/300 level MATH courses with prerequisites from MATH_PREREQUISITES
    for math_code, prereq_data in MATH_PREREQUISITES.items():
        if math_code in courses:
            prereqs = prereq_data.get("prereq", [])
            if prereqs and not courses[math_code].get("prerequisites"):
                courses[math_code]["prerequisites"] = prereqs

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
