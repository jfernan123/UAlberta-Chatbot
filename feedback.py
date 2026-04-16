# feedback.py
"""
Feedback collection system for UAlberta Math & Stats Chatbot
Records user ratings and feedback for response improvement
"""

import json
import os
from datetime import datetime
from typing import Optional, List, Dict

FEEDBACK_FILE = "data/feedback.json"


def ensure_feedback_dir():
    """Create data directory if it doesn't exist"""
    os.makedirs("data", exist_ok=True)


def load_feedback() -> List[Dict]:
    """Load all feedback entries from file"""
    ensure_feedback_dir()
    if not os.path.exists(FEEDBACK_FILE):
        return []

    with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []


def save_feedback(entries: List[Dict]):
    """Save all feedback entries to file"""
    ensure_feedback_dir()
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def record_feedback(
    question: str,
    response: str,
    rating: int,
    feedback_text: Optional[str] = None,
    session_id: Optional[str] = None,
) -> Dict:
    """
    Record a user's feedback on a response

    Args:
        question: The user's question
        response: The chatbot's response
        rating: 1 for thumbs up, -1 for thumbs down (or 1-5 for stars)
        feedback_text: Optional user comment
        session_id: Optional anonymous session identifier

    Returns:
        The recorded feedback entry
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "question": question,
        "response": response[:500]
        if len(response) > 500
        else response,  # Truncate long responses
        "rating": rating,
    }

    if feedback_text:
        entry["feedback_text"] = feedback_text

    if session_id:
        entry["session_id"] = session_id

    # Load existing and append
    entries = load_feedback()
    entries.append(entry)
    save_feedback(entries)

    return entry


def get_statistics() -> Dict:
    """Get summary statistics from feedback data"""
    entries = load_feedback()

    if not entries:
        return {
            "total_feedback": 0,
            "positive": 0,
            "negative": 0,
            "neutral": 0,
            "avg_rating": 0.0,
            "by_category": {},
        }

    positive = sum(1 for e in entries if e.get("rating", 0) > 0)
    negative = sum(1 for e in entries if e.get("rating", 0) < 0)
    neutral = sum(1 for e in entries if e.get("rating", 0) == 0)

    # Simple average (treating -1 as 0, 1 as 1 for averaging)
    ratings = [e.get("rating", 0) for e in entries]
    avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

    return {
        "total_feedback": len(entries),
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "avg_rating": round(avg_rating, 3),
    }


def get_low_rated_questions(limit: int = 10) -> List[Dict]:
    """Get questions with negative ratings"""
    entries = load_feedback()
    negative = [e for e in entries if e.get("rating", 0) < 0]
    negative.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return negative[:limit]


def get_unanswered_patterns() -> Dict:
    """Analyze question patterns that might need more content"""
    entries = load_feedback()

    # Simple keyword extraction from negative feedback
    question_words = {}
    for entry in entries:
        if entry.get("rating", 0) < 0:
            words = entry.get("question", "").lower().split()
            for word in words:
                if len(word) > 3:  # Skip short words
                    question_words[word] = question_words.get(word, 0) + 1

    # Sort by frequency
    sorted_words = sorted(question_words.items(), key=lambda x: x[1], reverse=True)

    return {
        "frequent_words_in_unsuccessful_queries": sorted_words[:20],
        "total_negative_feedback": len([e for e in entries if e.get("rating", 0) < 0]),
    }


if __name__ == "__main__":
    # Test the feedback system
    print("Testing feedback system...")

    # Record a test feedback
    test_entry = record_feedback(
        question="What courses can I take?",
        response="You can take Calculus and Linear Algebra.",
        rating=1,
    )
    print(f"Recorded test feedback: {test_entry}")

    # Get statistics
    stats = get_statistics()
    print(f"\nStatistics: {stats}")

    # Get low rated questions
    low_rated = get_low_rated_questions()
    print(f"\nLow rated questions: {low_rated}")
