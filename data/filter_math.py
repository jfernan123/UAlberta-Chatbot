"""
Filter pages_math.json to remove non-math/stats pages that slipped in via link-following.
Run from project root: conda run -n stat541 python data/filter_math.py
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(BASE, "data/pages_math.json")

with open(PATH, encoding="utf-8") as f:
    pages = json.load(f)

print(f"Input: {len(pages)} pages")

def is_relevant(page):
    url = page.get("url", "")
    # Keep department website pages
    if "ualberta.ca/en/mathematical-and-statistical-sciences" in url:
        return True
    # Keep calendar individual course pages for MATH/STAT
    if "preview_course_nopop" in url:
        for s in page.get("sections", []):
            import re
            if re.match(r"(MATH|STAT|MA PH) \d{3}", s.get("heading", "")):
                return True
        return False
    # Drop everything else (general catalog pages, other dept calendar pages, etc.)
    return False

filtered = [p for p in pages if is_relevant(p)]
print(f"After filtering: {len(filtered)} pages")

# Show removed URLs
removed = [p["url"] for p in pages if not is_relevant(p)]
for url in removed:
    print(f"  REMOVED: {url}")

with open(PATH, "w", encoding="utf-8") as f:
    json.dump(filtered, f, ensure_ascii=False, indent=2)
print(f"Saved to {PATH}")
