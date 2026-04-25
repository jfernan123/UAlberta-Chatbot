import json, re

with open("data/pages_calendar.json", encoding="utf-8") as f:
    pages = json.load(f)

for p in pages:
    for s in p.get("sections", []):
        heading = s.get("heading", "")
        content = s.get("content", "")
        if not re.match(r"(MATH|STAT) \d{3}", heading):
            continue
        m = re.search(r"((?:Pre|Co)requisite[s]?:.*?)(?:\s{2}|Notes:|$)", content)
        if not m:
            continue
        prereq_text = m.group(1)
        # Has both "one of" and something that looks like a hard requirement
        has_one_of = "one of" in prereq_text.lower()
        has_and = " and " in prereq_text.lower()
        if has_one_of and has_and:
            print(f"{heading}")
            print(f"  {prereq_text}")
            print()
