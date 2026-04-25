import json

with open("data/pages_calendar.json", encoding="utf-8") as f:
    pages = json.load(f)

targets = ["STAT 252", "MATH 214", "STAT 378", "MATH 225"]

for p in pages:
    for s in p.get("sections", []):
        heading = s.get("heading", "")
        if any(heading.startswith(t) for t in targets):
            print("URL:", p["url"])
            for sec in p["sections"]:
                print(f"  [{sec['heading']}]: {sec['content'][:300]}")
            print()
            break
