import json

with open("data/pages_calendar.json", encoding="utf-8") as f:
    pages = json.load(f)

print(f"Total pages: {len(pages)}")
print()

# Find honors/math program pages
for p in pages:
    url = p.get("url", "")
    if "preview_program" in url:
        # Check if it's honors math
        all_text = " ".join(
            s.get("heading","") + " " + s.get("content","")
            for s in p.get("sections", [])
        )
        if "honor" in all_text.lower() and "math" in all_text.lower():
            print("=== URL:", url)
            for s in p.get("sections", []):
                print(f"  [{s['heading']}]")
                print(f"    {s['content'][:300]}")
            print()

# Also check for entity pages
print("\n=== ENTITY PAGES ===")
for p in pages:
    url = p.get("url","")
    if "preview_entity" in url:
        print("URL:", url)
        for s in p.get("sections", [])[:2]:
            print(f"  [{s['heading']}]: {s['content'][:100]}")
