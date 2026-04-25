"""
Generate synthetic summary documents to improve retrieval for known hard queries.
Run from project root: conda run -n stat541 python data/generate_synthetic.py
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_page(pages, url_fragment):
    for p in pages:
        if url_fragment in p.get("url", ""):
            return p
    return None


def get_sections_text(page):
    if not page:
        return ""
    return " ".join(
        f"{s['heading']}: {s['content']}"
        for s in page.get("sections", [])
    )


def get_section(page, heading_fragment):
    if not page:
        return ""
    for s in page.get("sections", []):
        if heading_fragment.lower() in s["heading"].lower():
            return s["content"]
    return ""


with open(os.path.join(BASE, "data/pages_math.json"), encoding="utf-8") as f:
    math_pages = json.load(f)

with open(os.path.join(BASE, "data/pages_calendar.json"), encoding="utf-8") as f:
    cal_pages = json.load(f)

synthetic = []

# 1. MSc Statistics/Mathematics application process
how_to_apply = load_page(math_pages, "how-to-apply")
admissions_index = load_page(math_pages, "graduate-studies/admissions/index")
deadlines = load_page(math_pages, "deadlines-and-faqs")
msc_page = load_page(math_pages, "programs/master-of-science")
costs = load_page(math_pages, "graduate-studies/admissions/costs")

how_to_apply_text = get_sections_text(how_to_apply)
admissions_text = get_sections_text(admissions_index)
deadlines_text = get_sections_text(deadlines)
msc_text = get_sections_text(msc_page)

synthetic.append({
    "url": "https://www.ualberta.ca/en/mathematical-and-statistical-sciences/graduate-studies/admissions/how-to-apply.html",
    "sections": [{
        "heading": "How to Apply to the MSc Statistics or MSc Mathematics Graduate Program",
        "content": (
            "To apply to the MSc Statistics or MSc Mathematics (or Applied Mathematics, Mathematical Physics) "
            "graduate program at the University of Alberta Department of Mathematical and Statistical Sciences: "
            + how_to_apply_text[:2000]
        )
    }, {
        "heading": "MSc Statistics Program Requirements and Admission",
        "content": msc_text[:1500] + " " + admissions_text[:1000]
    }, {
        "heading": "Graduate Admissions Deadlines and FAQs for MSc Statistics",
        "content": deadlines_text[:1500]
    }]
})

# 2. First-year math courses listing
course_groupings = load_page(math_pages, "course-groupings-by-area")
first_year_page = load_page(math_pages, "first-year-courses/index")

first_year_sections = []
if course_groupings:
    for s in course_groupings.get("sections", []):
        h = s["heading"].lower()
        if any(kw in h for kw in ["calculus i", "calculus for", "linear algebra", "honors calculus"]):
            first_year_sections.append(f"{s['heading']}: {s['content']}")

# Also gather 100-level courses from calendar
first_year_courses = []
for p in cal_pages:
    for s in p.get("sections", []):
        heading = s.get("heading", "")
        import re
        m = re.match(r"(MATH|STAT) 1\d\d", heading)
        if m:
            first_year_courses.append(f"{heading}: {s['content'][:200]}")

first_year_content = " ".join(first_year_sections[:6])
if first_year_courses:
    first_year_content += " | Courses: " + "; ".join(first_year_courses[:20])

synthetic.append({
    "url": "https://www.ualberta.ca/en/mathematical-and-statistical-sciences/undergraduate-studies/courses/first-year-courses/index.html",
    "sections": [{
        "heading": "First Year Mathematics and Statistics Courses Available",
        "content": (
            "The Department of Mathematical and Statistical Sciences offers the following first-year (100-level) "
            "mathematics and statistics courses: " + first_year_content[:3000]
        )
    }]
})

# 3. 400-level STAT courses
stat_400_courses = []
for p in cal_pages:
    for s in p.get("sections", []):
        heading = s.get("heading", "")
        import re
        m = re.match(r"STAT [45]\d\d", heading)
        if m and "Course Career: Undergraduate" in s.get("content", ""):
            stat_400_courses.append(f"{heading}: {s['content'][:300]}")

synthetic.append({
    "url": "https://www.ualberta.ca/en/mathematical-and-statistical-sciences/undergraduate-studies/courses/",
    "sections": [{
        "heading": "400-Level STAT Courses Offered (Undergraduate)",
        "content": (
            "The following 400-level (senior) Statistics courses are offered by the Department of Mathematical "
            "and Statistical Sciences at the University of Alberta: "
            + "; ".join(stat_400_courses)
        )
    }]
})

# 4. Double major / programs summary
programs_index = load_page(math_pages, "undergraduate-studies/programs/index")
double_major_content = get_section(programs_index, "Double Majors")
honors_major_content = get_section(programs_index, "Honors versus Major")

# Get list of specific programs
program_pages = [p for p in math_pages if "undergraduate-studies/programs/" in p.get("url", "")
                 and "index" not in p["url"]]
program_summaries = []
for p in program_pages:
    name = p["url"].split("/")[-1].replace(".html", "").replace("-", " ").title()
    summary = get_sections_text(p)[:300]
    program_summaries.append(f"{name}: {summary}")

synthetic.append({
    "url": "https://www.ualberta.ca/en/mathematical-and-statistical-sciences/undergraduate-studies/programs/index.html",
    "sections": [{
        "heading": "Double Major in Mathematics and Statistics - Can I Double Major?",
        "content": (
            "Students can pursue a double major or combined honors in Mathematics and Statistics at the "
            "University of Alberta. " + double_major_content[:1500]
        )
    }, {
        "heading": "Honors vs Major in Mathematics and Statistics",
        "content": honors_major_content[:1500]
    }, {
        "heading": "All Undergraduate Programs in Mathematics and Statistics",
        "content": (
            "The following undergraduate degree programs are available in the Department of Mathematical "
            "and Statistical Sciences: " + "; ".join(p["url"].split("/")[-1].replace(".html","").replace("-"," ").title()
                                                      for p in program_pages)
            + ". " + " | ".join(program_summaries[:5])
        )
    }]
})

# 5. Consolidated Honors/Major Mathematics requirements (poid=84304)
def build_program_requirements(cal_pages, poid, program_label):
    """Consolidate all sections from a program page into a single readable document."""
    page = None
    for p in cal_pages:
        if f"poid={poid}" in p.get("url", ""):
            page = p
            break
    if not page:
        return f"Program page {poid} not found."

    lines = []
    current_section = None
    for s in page.get("sections", []):
        heading = s["heading"].strip()
        content = s["content"].strip()
        if not content:
            current_section = heading
            continue
        if current_section:
            lines.append(f"{current_section}:")
            current_section = None
        if heading in ("3 units from:", "6 units from:", "3 units from"):
            lines.append(f"  Choose {heading} {content}")
        else:
            lines.append(f"{heading}: {content}")
    return "\n".join(lines)


math_req = build_program_requirements(cal_pages, "84304", "Mathematics")
stat_req = build_program_requirements(cal_pages, "84315", "Statistics")

synthetic.append({
    "url": "https://calendar.ualberta.ca/preview_program.php?catoid=56&poid=84304",
    "sections": [{
        "heading": "Honors in Mathematics Requirements (63 units) - Full Course List",
        "content": (
            "Honors in Mathematics at the University of Alberta requires 63 units. "
            "This is the complete list of required courses for the Honors Mathematics program:\n"
            + math_req
        )
    }, {
        "heading": "Major in Mathematics Requirements (51 units) - Full Course List",
        "content": (
            "Major in Mathematics at the University of Alberta requires 51 units. "
            "This is the complete list of required courses for the Mathematics Major program:\n"
            + math_req
        )
    }]
})

synthetic.append({
    "url": "https://calendar.ualberta.ca/preview_program.php?catoid=56&poid=84315",
    "sections": [{
        "heading": "Honors in Statistics Requirements (66 units) - Full Course List",
        "content": (
            "Honors in Statistics at the University of Alberta requires 66 units. "
            "This is the complete list of required courses for the Honors Statistics program:\n"
            + stat_req
        )
    }, {
        "heading": "Major in Statistics Requirements (54 units) - Full Course List",
        "content": (
            "Major in Statistics at the University of Alberta requires 54 units. "
            "This is the complete list of required courses for the Statistics Major program:\n"
            + stat_req
        )
    }]
})


out_path = os.path.join(BASE, "data/pages_synthetic.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(synthetic, f, ensure_ascii=False, indent=2)

print(f"Wrote {len(synthetic)} synthetic pages to {out_path}")
for p in synthetic:
    for s in p["sections"]:
        print(f"  [{s['heading'][:70]}] {len(s['content'])} chars")
