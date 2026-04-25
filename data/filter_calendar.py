"""
Filter pages_calendar.json to remove non-math/stats program pages.
Run from project root: conda run -n stat541 python data/filter_calendar.py
"""
import json
import re
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT = os.path.join(BASE, "data/pages_calendar.json")
OUTPUT = os.path.join(BASE, "data/pages_calendar.json")  # overwrite in place

with open(INPUT, encoding="utf-8") as f:
    pages = json.load(f)

print(f"Input: {len(pages)} pages")

def is_math_stat_relevant(page):
    url = page.get("url", "")
    all_text = " ".join(
        s.get("heading","") + " " + s.get("content","")
        for s in page.get("sections", [])
    )

    # Always keep individual course pages (preview_course_nopop)
    if "preview_course_nopop" in url:
        # Only keep MATH, STAT, or MA PH courses
        headings = [s.get("heading","") for s in page.get("sections", [])]
        for h in headings:
            if re.match(r"(MATH|STAT|MA PH) \d{3}", h):
                return True
        return False  # drop non-math/stat individual course pages

    # For program pages, keep ONLY math/stats department programs
    if "preview_program" in url:
        # Require explicit mention of the department or "BSc in Math/Stat" language
        strict_signals = [
            "Mathematical and Statistical Sciences",
            "mathematical and statistical",
            "BSc (Mathematics)",
            "BSc (Statistics)",
            "BSc Honors in Mathematics",
            "BSc Honors in Statistics",
            "Major in Mathematics",
            "Major in Statistics",
            "Honors in Mathematics",
            "Honors in Statistics",
            "Combined Honors in Mathematics",
        ]
        return any(sig.lower() in all_text.lower() for sig in strict_signals)

    # Drop all content.php pages - they're calendar meta-pages (indexes, amendments, etc.)
    if "content.php" in url:
        return False

    # Drop entity pages (Faculty pages - Engineering, Medicine, Arts, Business, etc.)
    if "preview_entity" in url:
        return False

    # Drop search, help, index, misc pages
    if any(x in url for x in ["search_advanced", "help.php", "index.php", "catalog_list", "misc/"]):
        return False

    return True  # keep anything else by default


filtered = [p for p in pages if is_math_stat_relevant(p)]

# Also remove &print duplicates
seen_base_urls = set()
deduped = []
for p in filtered:
    url = p.get("url", "")
    base = url.replace("&print", "").rstrip("/")
    if base not in seen_base_urls:
        seen_base_urls.add(base)
        deduped.append(p)

print(f"After filtering: {len(deduped)} pages")

# Show breakdown
course_count = sum(1 for p in deduped if "preview_course_nopop" in p.get("url",""))
program_count = sum(1 for p in deduped if "preview_program" in p.get("url",""))
other_count = len(deduped) - course_count - program_count
print(f"  Course pages: {course_count}")
print(f"  Program pages: {program_count}")
print(f"  Other pages: {other_count}")

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(deduped, f, ensure_ascii=False, indent=2)
print(f"Saved to {OUTPUT}")
