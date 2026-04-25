import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatbot_graph import build_chatbot

# ── Easy: direct lookups, single source of truth ─────────────────────────────
EASY = [
    # Prerequisites - simple
    "What are the prerequisites for STAT 471?",
    "What are the prerequisites for MATH 209?",
    "What are the prerequisites for STAT 265?",
    "What are the prerequisites for STAT 378?",
    "Does STAT 151 have any prerequisites?",

    # Prerequisites - mixed OR and hard requirements
    "What are the prerequisites for STAT 266?",
    "What are the prerequisites for MATH 217?",
    "What are the prerequisites for STAT 353?",
    "What are the prerequisites for MATH 334?",
    "What are the prerequisites for MATH 225?",

    # Course listings by level
    "What first year math courses are available?",
    "What 400-level STAT courses are offered?",
    "What 300-level STAT courses are available?",
    "What second year statistics courses are there?",

    # Support and services
    "What is the Decima Robinson Support Centre?",
    "Where can I get help with my calculus homework?",
    "Is there tutoring available for statistics students?",
]

# ── Medium: requires combining info or understanding program structure ─────────
MEDIUM = [
    # Program comparisons
    "What is the difference between an Honors and a Major in Mathematics?",
    "What is the difference between STAT 151 and STAT 265?",
    "What is the difference between the Mathematics and Statistics programs?",

    # Program requirements
    "What are the requirements for honors math?",
    "What are the requirements for the major in statistics?",
    "How many units do I need for a minor in mathematics?",

    # Programs overview
    "What programs are available in Mathematics and Statistics?",
    "What is the Data Science program?",
    "What is the Applied Mathematics program?",
    "Can I double major in Math and Statistics?",

    # Graduate
    "What is the MDP program?",
    "How do I apply to the MSc Statistics program?",
    "What is the PhD program in Mathematics?",
    "Is there funding available for graduate students?",
]

# ── Hard: planning, multi-step reasoning, or requires synthesizing sources ────
HARD = [
    # Path planning
    "I want to study statistics. What courses should I take in first year?",
    "I've completed STAT 265 and STAT 281. What 300-level STAT courses can I take?",
    "What is the engineering calculus sequence?",
    "What courses do I need before taking STAT 471?",

    # Career / outcomes
    "What careers can I pursue with a Statistics degree?",
    "What jobs are available for Data Science graduates?",

    # Research and opportunities
    "Are there research opportunities for undergrad students?",
    "Is there a study abroad program for math students?",
    "What student clubs are available for math and stats students?",
    "What scholarships are available for math students?",

    # Consulting / training
    "What is the Statistical Consulting service?",
    "Does the department offer any consulting or training for researchers?",

    # Edge cases
    "I'm a high school student interested in math. What outreach programs exist?",
    "What is the difference between the honors statistics and honors mathematics programs?",
    "If I complete STAT 151, what statistics courses can I take next?",
]

TEST_QUESTIONS = EASY + MEDIUM + HARD


def main():
    print("Loading chatbot...")
    bot = build_chatbot()

    categories = [
        ("EASY", EASY),
        ("MEDIUM", MEDIUM),
        ("HARD", HARD),
    ]

    for category, questions in categories:
        print(f"\n{'=' * 70}")
        print(f"  {category} ({len(questions)} questions)")
        print(f"{'=' * 70}")

        for i, question in enumerate(questions, 1):
            print(f"\n[{i}] {question}")
            print("-" * 70)
            answer = bot(question)
            print(answer)

    for i, question in enumerate(TEST_QUESTIONS, 1):
        print(f"\n[{i}/{len(TEST_QUESTIONS)}] {question}")
        print("-" * 70)
        for chunk in bot(question):
            print(chunk, end="", flush=True)
        print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
