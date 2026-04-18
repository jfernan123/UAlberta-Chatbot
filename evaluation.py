# evaluation.py
"""
Evaluation suite for UAlberta Math & Stats RAG Chatbot
Based on GLUE/ROUGE style metrics for retrieval and generation evaluation
"""

import json
import re
from dataclasses import dataclass
from typing import List, Dict, Optional
from collections import Counter

# =============================================================================
# Test Cases with Expected Keywords (derived from scraped content)
# =============================================================================

TEST_CASES = [
    {
        "question": "What courses can I take in first year?",
        "expected_keywords": [
            "Calculus",
            "Linear Algebra",
            "Statistics",
            "MATH",
            "STAT",
        ],
        "expected_topics": ["Calculus", "Linear Algebra", "Statistics"],
        "category": "courses",
    },
    {
        "question": "What's the difference between Honors and Major programs?",
        "expected_keywords": ["Honors", "Major", "postgraduate", "research", "rigour"],
        "expected_topics": [
            "Honors programs",
            "Major programs",
            "postgraduate degrees",
        ],
        "category": "programs",
    },
    {
        "question": "What programs are available in Mathematics and Statistics?",
        "expected_keywords": [
            "Mathematics",
            "Statistics",
            "Applied Mathematics",
            "Honors",
            "Major",
            "Minor",
        ],
        "expected_topics": [
            "Mathematics",
            "Statistics",
            "Applied Mathematics",
            "Mathematical Physics",
        ],
        "category": "programs",
    },
    {
        "question": "What is Linear Algebra?",
        "expected_keywords": [
            "Linear Algebra",
            "Matrix",
            "Vector",
            "MATH 125",
            "MATH 127",
        ],
        "expected_topics": ["Linear Algebra"],
        "category": "courses",
    },
    {
        "question": "What Calculus courses are offered?",
        "expected_keywords": [
            "Calculus",
            "MATH 117",
            "MATH 118",
            "MATH 134",
            "MATH 144",
        ],
        "expected_topics": ["Calculus"],
        "category": "courses",
    },
    {
        "question": "Can I double major in Mathematics and Statistics?",
        "expected_keywords": [
            "Double Major",
            "Minor",
            "BSc",
            "Faculty of Science",
            "Faculty of Arts",
        ],
        "expected_topics": ["Double Majors", "Minors"],
        "category": "programs",
    },
    {
        "question": "What help is available for math courses?",
        "expected_keywords": [
            "Decima Robinson Support Centre",
            "help",
            "tutoring",
            "mssugrd",
        ],
        "expected_topics": ["Decima Robinson Support Centre"],
        "category": "support",
    },
    {
        "question": "What are the requirements for Honors in Mathematics?",
        "expected_keywords": ["Honors", "GPA", "MATH", "department approval"],
        "expected_topics": ["Honors Mathematics"],
        "category": "programs",
    },
    {
        "question": "What is the Statistics program?",
        "expected_keywords": [
            "Statistics",
            "collecting",
            "analyzing",
            "interpreting data",
            "Honors",
            "Major",
            "Minor",
        ],
        "expected_topics": ["Statistics program overview"],
        "category": "programs",
    },
    {
        "question": "What is the Mathematics program?",
        "expected_keywords": [
            "Mathematics",
            "analysis",
            "geometry",
            "number theory",
            "Honors",
            "Major",
            "Minor",
        ],
        "expected_topics": ["Mathematics program overview"],
        "category": "programs",
    },
]


# =============================================================================
# Data Classes for Evaluation Results
# =============================================================================


@dataclass
class RetrievalResult:
    """Results from retrieval evaluation"""

    question: str
    k: int
    num_relevant_retrieved: int
    num_total_retrieved: int
    num_relevant_total: int
    precision: float
    recall: float
    retrieved_doc_sources: List[str]


@dataclass
class GenerationResult:
    """Results from generation evaluation"""

    question: str
    response: str
    expected_keywords: List[str]
    found_keywords: List[str]
    missing_keywords: List[str]
    keyword_coverage: float
    response_length: int
    context_used: bool


@dataclass
class EvaluationResult:
    """Combined evaluation result for a test case"""

    test_case: Dict
    retrieval: Optional[RetrievalResult]
    generation: GenerationResult
    rouge_l: float
    overall_score: float


# =============================================================================
# Retrieval Metrics
# =============================================================================


def extract_keywords_from_chunks(chunks: List) -> set:
    """Extract key terms from retrieved chunks"""
    keywords = set()
    for chunk in chunks:
        text = chunk.page_content.lower()
        # Extract URLs as source identifiers
        if "source:" in text:
            url_match = re.search(r"source:\s*(https?://[^\s]+)", text)
            if url_match:
                keywords.add(url_match.group(1))
        # Extract potential topic keywords (capitalized terms)
        for word in re.findall(r"\b[A-Z][a-z]+\b", text):
            if len(word) > 2:
                keywords.add(word.lower())
    return keywords


def evaluate_retrieval(
    question: str, retrieved_docs: List, k: int = 4
) -> RetrievalResult:
    """
    Evaluate retrieval quality using Precision@K and Recall@K

    Since we don't have explicit relevance labels, we use keyword matching
    to estimate relevance based on the question content.
    """
    # Extract key terms from question for relevance estimation
    question_terms = set(re.findall(r"\b[a-zA-Z]{3,}\b", question.lower()))

    # Estimate relevant docs based on content overlap
    num_relevant_retrieved = 0
    retrieved_sources = []

    for doc in retrieved_docs[:k]:
        doc_text = doc.page_content.lower()
        doc_terms = set(re.findall(r"\b[a-zA-Z]{3,}\b", doc_text))
        overlap = len(question_terms & doc_terms)

        # Consider relevant if significant term overlap
        if overlap >= 2 or any(term in doc_text for term in question_terms):
            num_relevant_retrieved += 1

        # Track sources
        if "source:" in doc.page_content:
            match = re.search(r"source:\s*(https?://[^\s]+)", doc.page_content)
            if match:
                retrieved_sources.append(match.group(1))

    # For estimation, assume total relevant = retrieved (conservative)
    precision = num_relevant_retrieved / k if k > 0 else 0
    recall = num_relevant_retrieved / max(num_relevant_retrieved, 1)

    return RetrievalResult(
        question=question,
        k=k,
        num_relevant_retrieved=num_relevant_retrieved,
        num_total_retrieved=k,
        num_relevant_total=num_relevant_retrieved,
        precision=precision,
        recall=recall,
        retrieved_doc_sources=retrieved_sources,
    )


# =============================================================================
# Generation Metrics
# =============================================================================


def evaluate_keyword_coverage(response: str, expected_keywords: List[str]) -> tuple:
    """Calculate keyword coverage"""
    response_lower = response.lower()

    found = []
    missing = []

    for keyword in expected_keywords:
        # Check for keyword or its variations
        variations = [
            keyword.lower(),
            keyword.lower() + "s",  # plural
            keyword.lower() + "es",  # plural
        ]

        if any(var in response_lower for var in variations):
            found.append(keyword)
        else:
            missing.append(keyword)

    coverage = len(found) / len(expected_keywords) if expected_keywords else 0
    return found, missing, coverage


def compute_rouge_l(response: str, reference: str) -> float:
    """
    Compute ROUGE-L (Longest Common Subsequence) score
    Simplified implementation for single reference
    """

    def get_lcs(s1: str, s2: str) -> int:
        """Get longest common subsequence length"""
        m, n = len(s1), len(s2)
        if m == 0 or n == 0:
            return 0

        # Simple LCS implementation
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i - 1] == s2[j - 1]:
                    dp[i][j] = dp[i - 1][j - 1] + 1
                else:
                    dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

        return dp[m][n]

    # Tokenize
    response_tokens = response.lower().split()
    reference_tokens = reference.lower().split()

    if not response_tokens or not reference_tokens:
        return 0.0

    lcs_len = get_lcs(response_tokens, reference_tokens)

    # ROUGE-L precision
    precision = lcs_len / len(response_tokens) if response_tokens else 0
    # ROUGE-L recall
    recall = lcs_len / len(reference_tokens) if reference_tokens else 0

    # F-measure
    if precision + recall > 0:
        f_measure = 2 * precision * recall / (precision + recall)
    else:
        f_measure = 0

    return round(f_measure, 3)


def evaluate_faithfulness(response: str, context_docs: List) -> float:
    """
    Estimate faithfulness - whether response is grounded in context
    Simplified version: check if response keywords appear in context
    """
    if not context_docs:
        return 0.0

    response_terms = set(re.findall(r"\b[a-zA-Z]{4,}\b", response.lower()))
    context_text = " ".join(doc.page_content for doc in context_docs).lower()

    # Count how many response terms appear in context
    terms_in_context = sum(1 for term in response_terms if term in context_text)

    if response_terms:
        faithfulness = terms_in_context / len(response_terms)
    else:
        faithfulness = 0.0

    return round(faithfulness, 3)


def evaluate_generation(
    test_case: Dict, response: str, context_docs: List
) -> GenerationResult:
    """Evaluate generation quality"""
    expected_keywords = test_case.get("expected_keywords", [])

    found_keywords, missing_keywords, keyword_coverage = evaluate_keyword_coverage(
        response, expected_keywords
    )

    return GenerationResult(
        question=test_case["question"],
        response=response,
        expected_keywords=expected_keywords,
        found_keywords=found_keywords,
        missing_keywords=missing_keywords,
        keyword_coverage=keyword_coverage,
        response_length=len(response),
        context_used=len(context_docs) > 0,
    )


# =============================================================================
# Main Evaluation Runner
# =============================================================================


def run_evaluation_batched(
    chatbot_func, test_cases: List[Dict] = None, batch_size: int = 3
) -> List[EvaluationResult]:
    """
    Run evaluation in batches with progress reporting

    Args:
        chatbot_func: Function that takes a question and returns response string
        test_cases: Optional custom test cases (defaults to TEST_CASES)
        batch_size: Number of test cases per batch (default 3)

    Returns:
        List of EvaluationResult objects
    """
    if test_cases is None:
        test_cases = TEST_CASES

    results = []

    print("=" * 60)
    print("RAG EVALUATION SUITE (BATCHED)")
    print("=" * 60)
    print(f"Running {len(test_cases)} test cases in batches of {batch_size}...\n")

    for batch_start in range(0, len(test_cases), batch_size):
        batch_end = min(batch_start + batch_size, len(test_cases))
        batch = test_cases[batch_start:batch_end]

        print(f"\n--- Batch {batch_start // batch_size + 1}/{(len(test_cases) + batch_size - 1) // batch_size} ---")
        print(f"Progress: {batch_start}/{len(test_cases)} test cases completed\n")

        for i, test_case in enumerate(batch, batch_start + 1):
            question = test_case["question"]
            print(f"[{i}/{len(test_cases)}] Question: {question[:50]}...")

            try:
                # Get response
                response = chatbot_func(question)

                # Get context
                from retriever import load_retriever
                retriever = load_retriever()
                retrieved_docs = retriever.invoke(question)

                # Evaluate retrieval
                retrieval_result = evaluate_retrieval(question, retrieved_docs, k=4)

                # Evaluate generation
                generation_result = evaluate_generation(test_case, response, retrieved_docs)

                # Compute ROUGE-L
                reference = " ".join(test_case.get("expected_topics", []))
                rouge_l = compute_rouge_l(response, reference)

                # Overall score
                overall = (
                    0.3 * retrieval_result.precision
                    + 0.4 * generation_result.keyword_coverage
                    + 0.3 * rouge_l
                )

                result = EvaluationResult(
                    test_case=test_case,
                    retrieval=retrieval_result,
                    generation=generation_result,
                    rouge_l=rouge_l,
                    overall_score=round(overall, 3),
                )
                results.append(result)

                print(f"  - Precision@4: {retrieval_result.precision:.2f}")
                print(f"  - Keyword Coverage: {generation_result.keyword_coverage:.2f}")
                print(f"  - ROUGE-L: {rouge_l:.3f}")
                print(f"  - Overall: {overall:.3f}")

            except Exception as e:
                print(f"  - ERROR: {str(e)}")
                results.append(None)

        print(f"\n>>> Partial complete: {len(results)}/{len(test_cases)} results")

    return results


def run_evaluation(
    chatbot_func, test_cases: List[Dict] = None
) -> List[EvaluationResult]:
    """
    Run complete evaluation on all test cases

    Args:
        chatbot_func: Function that takes a question and returns (response, docs)
        test_cases: Optional custom test cases (defaults to TEST_CASES)

    Returns:
        List of EvaluationResult objects
    """
    if test_cases is None:
        test_cases = TEST_CASES

    results = []

    print("=" * 60)
    print("RAG EVALUATION SUITE")
    print("=" * 60)
    print(f"Running {len(test_cases)} test cases...\n")

    for i, test_case in enumerate(test_cases, 1):
        question = test_case["question"]
        print(f"[{i}/{len(test_cases)}] Question: {question[:50]}...")

        try:
            # Get response and retrieved docs
            response = chatbot_func(question)

            # Get context (we need to access the retriever)
            from retriever import load_retriever

            retriever = load_retriever()
            retrieved_docs = retriever.invoke(question)

            # Evaluate retrieval
            retrieval_result = evaluate_retrieval(question, retrieved_docs, k=4)

            # Evaluate generation
            generation_result = evaluate_generation(test_case, response, retrieved_docs)

            # Compute ROUGE-L (using expected topics as reference)
            reference = " ".join(test_case.get("expected_topics", []))
            rouge_l = compute_rouge_l(response, reference)

            # Calculate overall score (weighted average)
            overall = (
                0.3 * retrieval_result.precision
                + 0.4 * generation_result.keyword_coverage
                + 0.3 * rouge_l
            )

            result = EvaluationResult(
                test_case=test_case,
                retrieval=retrieval_result,
                generation=generation_result,
                rouge_l=rouge_l,
                overall_score=round(overall, 3),
            )
            results.append(result)

            print(f"  - Precision@4: {retrieval_result.precision:.2f}")
            print(f"  - Keyword Coverage: {generation_result.keyword_coverage:.2f}")
            print(f"  - ROUGE-L: {rouge_l:.3f}")
            print(f"  - Overall: {overall:.3f}")

        except Exception as e:
            print(f"  - ERROR: {str(e)}")
            results.append(None)

    return results


def print_evaluation_summary(results: List[EvaluationResult]):
    """Print summary statistics"""
    valid_results = [r for r in results if r is not None]

    if not valid_results:
        print("\nNo valid results to summarize.")
        return

    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)

    # Aggregate metrics
    avg_precision = sum(r.retrieval.precision for r in valid_results) / len(
        valid_results
    )
    avg_coverage = sum(r.generation.keyword_coverage for r in valid_results) / len(
        valid_results
    )
    avg_rouge = sum(r.rouge_l for r in valid_results) / len(valid_results)
    avg_overall = sum(r.overall_score for r in valid_results) / len(valid_results)

    print(f"\nMetrics (averaged across {len(valid_results)} test cases):")
    print(f"  - Retrieval Precision@4:     {avg_precision:.3f}")
    print(f"  - Keyword Coverage:          {avg_coverage:.3f}")
    print(f"  - ROUGE-L:                   {avg_rouge:.3f}")
    print(f"  - Overall Score:             {avg_overall:.3f}")

    # Category breakdown
    categories = {}
    for r in valid_results:
        cat = r.test_case.get("category", "unknown")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r.overall_score)

    print(f"\nBy Category:")
    for cat, scores in categories.items():
        print(f"  - {cat}: {sum(scores) / len(scores):.3f} (n={len(scores)})")

    # Individual scores
    print(f"\nIndividual Test Case Scores:")
    for r in valid_results:
        q_short = r.test_case["question"][:40]
        print(f"  [{r.overall_score:.3f}] {q_short}...")


# =============================================================================
# CLI Entry Point
# =============================================================================

if __name__ == "__main__":
    from chatbot import build_chatbot

    print("Building chatbot...")
    bot = build_chatbot()

    # Run evaluation (batched with progress)
    results = run_evaluation_batched(bot, batch_size=3)

    # Print summary
    print_evaluation_summary(results)
