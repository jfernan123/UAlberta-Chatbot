import json

with open("data/pages_math.json", encoding="utf-8") as f:
    math = json.load(f)
with open("data/course_graph.json") as f:
    graph = json.load(f)

print("Math dept pages:")
for p in math:
    slug = p["url"].split("mathematical-and-statistical-sciences/")[-1][:70]
    print(" ", slug)

courses = graph["courses"]
print(f"\nTotal courses: {len(courses)}")
print("Sequences:", list(graph["sequences"].keys()))

# Show a sample of STAT courses
print("\nSome STAT courses:")
for code, info in sorted(courses.items()):
    if code.startswith("STAT"):
        prereqs = info.get("prerequisites", [])
        print(f"  {code}: {info['name']} | prereqs: {prereqs}")
