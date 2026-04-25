import json

with open("data/pages_calendar.json", encoding="utf-8") as f:
    pages = json.load(f)

# Show full content of STAT 252 page
for p in pages:
    for s in p.get("sections", []):
        if s.get("heading", "").startswith("STAT 252"):
            print("URL:", p["url"])
            for sec in p["sections"]:
                print(f"\n[{sec['heading']}]")
                print(sec["content"])
            break
