import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from chatbot import build_chatbot

TEST_QUESTIONS = [
    "What are the prerequisites for STAT 471?",
    "What are the prerequisites for MATH 209?",
    "What is the MDP program?",
    "What is the difference between an Honors and a Major in Mathematics?",
    "What first year math courses are available?",
    "What is the Decima Robinson Support Centre?",
    "What programs are available in Mathematics and Statistics?",
    "Can I double major in Math and Statistics?",
    "How do I apply to the MSc Statistics program?",
    "What 400-level STAT courses are offered?",
]


def main():
    print("Loading chatbot...")
    bot = build_chatbot()

    print(f"Running {len(TEST_QUESTIONS)} questions...\n")
    print("=" * 70)

    for i, question in enumerate(TEST_QUESTIONS, 1):
        print(f"\n[{i}/{len(TEST_QUESTIONS)}] {question}")
        print("-" * 70)
        answer = bot(question)
        print(answer)
        print("=" * 70)


if __name__ == "__main__":
    main()
