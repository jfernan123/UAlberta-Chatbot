# analytics.py
"""
Feedback analytics for UAlberta Math & Stats Chatbot
Analyzes feedback patterns to identify areas for improvement
"""

import json
from collections import Counter
from datetime import datetime
from feedback import load_feedback, get_statistics, get_low_rated_questions


def categorize_question(question: str) -> str:
    """Categorize a question based on keywords"""
    q = question.lower()

    if any(
        word in q
        for word in ["course", "calculus", "linear algebra", "math", "stat", "class"]
    ):
        return "courses"
    elif any(
        word in q
        for word in ["program", "honors", "major", "minor", "degree", "specialization"]
    ):
        return "programs"
    elif any(word in q for word in ["help", "support", "tutor", "advisor", "contact"]):
        return "support"
    elif any(word in q for word in ["requirement", "admission", "gpa", "average"]):
        return "admissions"
    else:
        return "other"


def analyze_by_category() -> dict:
    """Analyze feedback broken down by question category"""
    entries = load_feedback()

    categories = {}
    for entry in entries:
        cat = categorize_question(entry.get("question", ""))
        if cat not in categories:
            categories[cat] = {"positive": 0, "negative": 0, "questions": []}

        rating = entry.get("rating", 0)
        if rating > 0:
            categories[cat]["positive"] += 1
        elif rating < 0:
            categories[cat]["negative"] += 1

        categories[cat]["questions"].append(
            {"question": entry.get("question", ""), "rating": rating}
        )

    # Calculate percentages
    for cat, data in categories.items():
        total = data["positive"] + data["negative"]
        if total > 0:
            data["positive_pct"] = round(100 * data["positive"] / total, 1)
            data["negative_pct"] = round(100 * data["negative"] / total, 1)
        else:
            data["positive_pct"] = 0
            data["negative_pct"] = 0

    return categories


def get_improvement_recommendations() -> list:
    """Generate actionable improvement recommendations"""
    recommendations = []

    stats = get_statistics()
    categories = analyze_by_category()
    low_rated = get_low_rated_questions()

    # Check overall sentiment
    if stats["total_feedback"] > 0:
        sentiment = stats["positive"] / stats["total_feedback"]

        if sentiment > 0.7:
            recommendations.append(
                "✅ Overall sentiment is positive (>70%). The chatbot is performing well!"
            )
        elif sentiment > 0.5:
            recommendations.append(
                "⚠️ Overall sentiment is neutral (50-70%). Room for improvement."
            )
        else:
            recommendations.append(
                "❌ Overall sentiment is low (<50%). Significant improvements needed."
            )

    # Check categories
    for cat, data in categories.items():
        if data.get("negative", 0) > data.get("positive", 0):
            recommendations.append(
                f"❌ Category '{cat}' has more negative than positive feedback. Consider adding more {cat} content."
            )

    # Check for patterns in low-rated questions
    if low_rated:
        keywords = []
        for entry in low_rated[:5]:
            q = entry.get("question", "").lower()
            words = [w for w in q.split() if len(w) > 4]
            keywords.extend(words[:3])  # Top 3 words per question

        common = Counter(keywords).most_common(5)
        if common:
            rec = f"⚠️ Users frequently ask about: {', '.join([w[0] for w in common])}"
            recommendations.append(rec)

    # Check for unanswered topics
    if not categories.get("courses", {}).get("positive", 0) > 0:
        recommendations.append(
            "💡 No positive feedback for courses yet. Consider adding more course details."
        )

    if not categories.get("programs", {}).get("positive", 0) > 0:
        recommendations.append(
            "💡 No positive feedback for programs yet. Ensure program pages are well indexed."
        )

    # Correlation with evaluation (check for topic overlap)
    if low_rated:
        low_topics = set()
        for entry in low_rated:
            q = entry.get("question", "").lower()
            if "mdp" in q:
                low_topics.add("MDP")
            if "honors" in q or "honour" in q:
                low_topics.add("Honors")
            if "statistic" in q:
                low_topics.add("Statistics")
            if "mathematic" in q:
                low_topics.add("Mathematics")
            if "course" in q:
                low_topics.add("Courses")

        if low_topics:
            recommendations.append(
                f"📊 Low-rated topics: {', '.join(sorted(low_topics))}"
            )

    return recommendations


def generate_report() -> str:
    """Generate a complete analytics report"""
    stats = get_statistics()
    categories = analyze_by_category()
    recommendations = get_improvement_recommendations()
    low_rated = get_low_rated_questions()

    report = []
    report.append("=" * 60)
    report.append("UAlberta Chatbot Feedback Analytics Report")
    report.append("=" * 60)
    report.append(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Overall stats
    report.append("\n\n--- OVERALL STATISTICS ---")
    for key, val in stats.items():
        report.append(f"  {key}: {val}")

    # Categories
    report.append("\n\n--- FEEDBACK BY CATEGORY ---")
    for cat, data in categories.items():
        report.append(f"\n  {cat.upper()}:")
        report.append(
            f"    Positive: {data.get('positive', 0)} ({data.get('positive_pct', 0)}%)"
        )
        report.append(
            f"    Negative: {data.get('negative', 0)} ({data.get('negative_pct', 0)}%)"
        )

    # Low rated
    if low_rated:
        report.append("\n\n--- QUESTIONS NEEDING ATTENTION ---")
        for entry in low_rated[:5]:
            report.append(f"  - {entry.get('question', '')}")

    # Recommendations
    if recommendations:
        report.append("\n\n--- RECOMMENDATIONS ---")
        for rec in recommendations:
            report.append(f"  {rec}")

    report.append("\n\n" + "=" * 60)

    return "\n".join(report)


def print_report():
    """Print report to console"""
    print(generate_report())


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "stats":
            stats = get_statistics()
            print(json.dumps(stats, indent=2))
        elif sys.argv[1] == "categories":
            cats = analyze_by_category()
            print(json.dumps(cats, indent=2))
        elif sys.argv[1] == "low":
            low = get_low_rated_questions()
            print(json.dumps(low, indent=2))
        else:
            print("Usage: python analytics.py [stats|categories|low]")
    else:
        print_report()
