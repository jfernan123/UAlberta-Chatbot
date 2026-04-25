# evaluation.py
"""
Evaluation suite for UAlberta Math & Stats RAG Chatbot
Based on GLUE/ROUGE style metrics for retrieval and generation evaluation

Optional: Set ENABLE_LLM_JUDGE=True to enable LLM-as-Judge evaluation
"""

import json
import re
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional
from collections import Counter

# Enable/disable LLM-as-Judge evaluation (slower but more comprehensive)
ENABLE_LLM_JUDGE = os.environ.get("ENABLE_LLM_JUDGE", "false").lower() == "true"
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "qwen3:0.6b")

# =============================================================================
# LLM-as-Judge Evaluator (Optional)
# =============================================================================

# Lazy-loaded judge to avoid initialization overhead
_judge_chain = None


def _get_judge_chain():
    """Get or create the LLM-as-Judge chain."""
    global _judge_chain
    if _judge_chain is None:
        from langchain_ollama import ChatOllama
        from langchain_core.prompts import ChatPromptTemplate
        import warnings

        warnings.filterwarnings("ignore")

        llm = ChatOllama(model=JUDGE_MODEL)

        judge_prompt = """Rate this answer. Output JSON only, keys h,a,r,c (0-1):

Q: {question}
A: {response}

JSON:"""

        _judge_chain = ChatPromptTemplate.from_template(judge_prompt) | llm

    return _judge_chain


def evaluate_with_llm_judge(
    question: str, response: str, context: str = ""
) -> Optional[Dict]:
    """
    Use LLM to judge response quality.

    Returns dict with helpfulness, accuracy, relevance, completeness scores
    or None if LLM judge is disabled.
    """
    if not ENABLE_LLM_JUDGE:
        return None

    try:
        import json
        import re

        chain = _get_judge_chain()
        result = chain.invoke(
            {"question": question, "response": response, "context": context[:1000]}
        )

        content = result.content

        try:
            data = json.loads(content)
            h = data.get("h", data.get("helpfulness", 0))
            a = data.get("a", data.get("accuracy", 0))
            r = data.get("r", data.get("relevance", 0))
            c = data.get("c", data.get("completeness", 0))
            return {
                "helpfulness": float(h),
                "accuracy": float(a),
                "relevance": float(r),
                "completeness": float(c),
            }
        except json.JSONDecodeError:
            match = re.search(r"\{[^}]+\}", content)
            if match:
                data = json.loads(match.group())
                h = data.get("h", data.get("helpfulness", 0))
                a = data.get("a", data.get("accuracy", 0))
                r = data.get("r", data.get("relevance", 0))
                c = data.get("c", data.get("completeness", 0))
                return {
                    "helpfulness": float(h),
                    "accuracy": float(a),
                    "relevance": float(r),
                    "completeness": float(c),
                }
            return None
    except Exception as e:
        print(f"LLM Judge error: {e}")
        return None


# =============================================================================
# Test Cases with Expected Keywords (derived from scraped content)
# =============================================================================

TEST_CASES = [
    {
        "question": "What courses can I take in first year?",
        "expected_keywords": [
            "MATH 117",
            "MATH 118",
            "courses",
            "MATH 136",
            "MATH 146",
            "MATH 156",
        ],
        "expected_topics": ["First-year courses"],
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
            "MATH 100",
            "MATH 101",
            "MATH 201",
            "MATH 209",
        ],
        "expected_topics": ["Calculus courses"],
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
        "expected_keywords": ["Honors", "MATH", "department approval", "GPA"],
        "expected_topics": ["Honors Mathematics"],
        "category": "programs",
    },
    {
        "question": "What is the MDP program?",
        "expected_keywords": [
            "MDP",
            "Modelling",
            "Data",
            "Predictions",
            "master",
            "data science",
            "16 months",
        ],
        "expected_topics": ["MDP program"],
        "category": "programs",
    },
    {
        "question": "What courses are offered for undergraduate math students?",
        "expected_keywords": [
            "MATH 160",
            "MATH 260",
            "Elementary Education",
            "Higher Arithmetic",
            "Mathematical Reasoning",
        ],
        "expected_topics": ["Undergraduate courses (Education)"],
        "category": "courses",
    },
    {
        "question": "What is the Statistics program?",
        "expected_keywords": [
            "Statistics",
            "data analysts",
            "actuaries",
            "biostatisticians",
            "Major",
            "Minor",
            "Associate Statistician",
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
            "Applied Mathematics",
        ],
        "expected_topics": ["Mathematics program overview"],
        "category": "programs",
    },
    {
        "question": "What are the prerequisites for MATH 209?",
        "expected_keywords": ["MATH 101", "prerequisite"],
        "expected_topics": ["MATH 209 prerequisites"],
        "category": "prerequisites",
    },
    {
        "question": "What do I need before taking STAT 266?",
        "expected_keywords": ["STAT 265", "MATH 209"],
        "expected_topics": ["STAT 266 prerequisites"],
        "category": "prerequisites",
    },
    {
        "question": "What courses can I take after completing MATH 117?",
        "expected_keywords": ["MATH 118", "MATH 217"],
        "expected_topics": ["Honors calculus sequence"],
        "category": "prerequisites",
    },
    {
        "question": "What courses can I take without any prerequisites?",
        "expected_keywords": ["MATH 100", "MATH 117", "STAT 151", "entry"],
        "expected_topics": ["Entry-level courses"],
        "category": "prerequisites",
    },
    {
        "question": "What MATH courses do I need before STAT 265?",
        "expected_keywords": ["MATH 209", "MATH 214", "MATH 217"],
        "expected_topics": ["STAT 265 MATH requirements"],
        "category": "prerequisites",
    },
    {
        "question": "What graduate MATH courses are available?",
        "expected_keywords": ["MATH 505", "MATH 506", "MATH 515"],
        "expected_topics": ["Graduate courses"],
        "category": "level_specific",
    },
    {
        "question": "What senior STAT courses are available?",
        "expected_keywords": ["STAT 471", "STAT 479", "STAT 413"],
        "expected_topics": ["Senior courses"],
        "category": "level_specific",
    },
    {
        "question": "What graduate courses are there?",
        "expected_keywords": ["MATH", "STAT", "500"],
        "expected_topics": ["Graduate MATH and STAT"],
        "category": "level_specific",
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
    keywords_in_data: List[str]
    keywords_not_in_data: List[str]


@dataclass
class EvaluationResult:
    """Combined evaluation result for a test case"""

    test_case: Dict
    retrieval: Optional[RetrievalResult]
    generation: GenerationResult
    rouge_l: float
    overall_score: float
    judge_scores: Optional[Dict] = None
    judge_issues: Optional[List[str]] = None
    judge_hallucinations: Optional[List[str]] = None
    judge_suggestions: Optional[List[str]] = None
    response: Optional[str] = None


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

    # Estimate: assume corpus contains 2× the number retrieved as relevant
    precision = num_relevant_retrieved / k if k > 0 else 0
    estimated_total_relevant = max(num_relevant_retrieved * 2, 1)
    recall = num_relevant_retrieved / estimated_total_relevant

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

    context_text = (
        " ".join(doc.page_content for doc in context_docs).lower()
        if context_docs
        else ""
    )

    keywords_in_data = []
    keywords_not_in_data = []
    for kw in expected_keywords:
        if kw.lower() in context_text:
            keywords_in_data.append(kw)
        else:
            keywords_not_in_data.append(kw)

    return GenerationResult(
        question=test_case["question"],
        response=response,
        expected_keywords=expected_keywords,
        found_keywords=found_keywords,
        missing_keywords=missing_keywords,
        keyword_coverage=keyword_coverage,
        response_length=len(response),
        context_used=len(context_docs) > 0,
        keywords_in_data=keywords_in_data,
        keywords_not_in_data=keywords_not_in_data,
    )


# =============================================================================
# Main Evaluation Runner
# =============================================================================


def run_evaluation(
    chatbot_func, test_cases: List[Dict] = None, retriever=None
) -> List[EvaluationResult]:
    """
    Run complete evaluation on all test cases

    Args:
        chatbot_func: Function that takes a question and returns (response, docs)
        test_cases: Optional custom test cases (defaults to TEST_CASES)
        retriever: Optional pre-built retriever (will be created if not provided)

    Returns:
        List of EvaluationResult objects
    """
    if test_cases is None:
        test_cases = TEST_CASES

    # Build retriever once outside the loop
    if retriever is None:
        from retrieval import load_retriever

        retriever = load_retriever()

    results = []

    print("=" * 60)
    print("RAG EVALUATION SUITE")
    print("=" * 60)
    print(f"Running {len(test_cases)} test cases...\n")

    for i, test_case in enumerate(test_cases, 1):
        question = test_case["question"]
        print(f"[{i}/{len(test_cases)}] Question: {question[:50]}...")

        try:
            # Get response (chatbot is a streaming generator)
            chunks = chatbot_func(question)
            full = "".join(chunks)
            # Strip trailing source block from evaluation text
            response = full.split("\n\n---\n**Sources**")[0]

            # Get context using pre-built retriever (no re-import inside loop)
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

            # Optional LLM-as-Judge evaluation
            judge_scores = None
            if ENABLE_LLM_JUDGE:
                context_str = "\n".join(doc.page_content for doc in retrieved_docs[:4])
                judge_scores = evaluate_with_llm_judge(question, response, context_str)
                if judge_scores:
                    avg_judge = sum(judge_scores.values()) / len(judge_scores)
                    print(f"  - LLM Judge: {avg_judge:.3f}")
                    print(
                        f"    (H:{judge_scores.get('helpfulness', 0):.1f} A:{judge_scores.get('accuracy', 0):.1f} R:{judge_scores.get('relevance', 0):.1f} C:{judge_scores.get('completeness', 0):.1f})"
                    )

            result = EvaluationResult(
                test_case=test_case,
                retrieval=retrieval_result,
                generation=generation_result,
                rouge_l=rouge_l,
                overall_score=round(overall, 3),
                judge_scores=judge_scores,
                response=response,
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

    # LLM Judge scores (if enabled)
    if ENABLE_LLM_JUDGE:
        print(f"\nLLM Judge Scores (experimental):")
        print(f"  - Note: ENABLE_LLM_JUDGE=true to enable")

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

    # Content availability check
    all_missing_from_data = []
    for r in valid_results:
        if r.generation.keywords_not_in_data:
            all_missing_from_data.extend(r.generation.keywords_not_in_data)

    if all_missing_from_data:
        print(f"\n[!] Keywords NOT found in any retrieved content:")
        for kw in set(all_missing_from_data):
            print(f"  - {kw}")
        print(f"\n  These keywords may not exist in the current data source.")


# =============================================================================
# CLI Entry Point
# =============================================================================

# Evaluation History Functions
# =============================================================================

HISTORY_FILE = "data/evaluation_history.json"


def compute_summary_metrics(results):
    """Compute summary metrics from results."""
    valid_results = [r for r in results if r is not None]
    if not valid_results:
        return None

    avg_precision = sum(r.retrieval.precision for r in valid_results) / len(
        valid_results
    )
    avg_coverage = sum(r.generation.keyword_coverage for r in valid_results) / len(
        valid_results
    )
    avg_rouge = sum(r.rouge_l for r in valid_results) / len(valid_results)
    avg_overall = sum(r.overall_score for r in valid_results) / len(valid_results)

    # Category breakdown
    by_category = {}
    for r in valid_results:
        cat = r.test_case.get("category", "unknown")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(r.overall_score)

    category_avg = {
        cat: sum(scores) / len(scores) for cat, scores in by_category.items()
    }

    return {
        "avg_precision": avg_precision,
        "avg_coverage": avg_coverage,
        "avg_rouge": avg_rouge,
        "avg_overall": avg_overall,
        "by_category": category_avg,
    }


def save_evaluation_history(results, model_name="qwen3:0.6b"):
    """Save evaluation results to history file for trend analysis."""
    # Compute metrics
    metrics = compute_summary_metrics(results)
    if metrics is None:
        print("No valid results to save.")
        return

    # Load existing history
    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        history = {"runs": []}

    # Create new run entry
    run_entry = {
        "timestamp": datetime.now().isoformat(),
        "model": model_name,
        "total_cases": len(results),
        "metrics": metrics,
    }

    # Append to history
    history["runs"].append(run_entry)

    # Save
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

    print(f"\nSaved evaluation to {HISTORY_FILE}")


CASES_FILE = "data/evaluation_cases.json"


def save_evaluation_cases(results, model_name="qwen3:0.6b"):
    """Save detailed evaluation case data to separate file."""
    valid_results = [r for r in results if r is not None]
    if not valid_results:
        print("No valid results to save.")
        return

    try:
        with open(CASES_FILE, "r") as f:
            history = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        history = {"runs": []}

    cases_data = []
    for r in valid_results:
        case = {
            "question": r.test_case.get("question", ""),
            "category": r.test_case.get("category", ""),
            "response": r.response or "",
            "metrics": {
                "precision": r.retrieval.precision if r.retrieval else 0,
                "coverage": r.generation.keyword_coverage,
                "rouge_l": r.rouge_l,
                "overall": r.overall_score,
            },
        }
        if r.judge_scores:
            case["judge_scores"] = r.judge_scores
            case["judge_avg"] = sum(r.judge_scores.values()) / len(r.judge_scores)
        if r.judge_issues:
            case["judge_issues"] = r.judge_issues
        if r.judge_hallucinations:
            case["judge_hallucinations"] = r.judge_hallucinations
        if r.judge_suggestions:
            case["judge_suggestions"] = r.judge_suggestions

        cases_data.append(case)

    run_entry = {
        "timestamp": datetime.now().isoformat(),
        "model": model_name,
        "total_cases": len(valid_results),
        "cases": cases_data,
    }

    history["runs"].append(run_entry)

    with open(CASES_FILE, "w") as f:
        json.dump(history, f, indent=2)

    print(f"Saved {len(cases_data)} cases to {CASES_FILE}")


def get_evaluation_history():
    """Load and return evaluation history."""
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"runs": []}


def print_history_summary():
    """Print summary of evaluation history."""
    history = get_evaluation_history()
    runs = history.get("runs", [])

    if not runs:
        print("No evaluation history found.")
        return

    print("\n" + "=" * 60)
    print("EVALUATION HISTORY")
    print("=" * 60)
    print(f"Total runs: {len(runs)}")

    # Print trend for overall score
    print("\nOverall Score Trend:")
    for i, run in enumerate(runs):
        score = run.get("metrics", {}).get("avg_overall", 0)
        model = run.get("model", "?")
        ts = run.get("timestamp", "")[:19]
        print(f"  Run {i + 1}: {score:.3f} ({model}) - {ts}")


# =============================================================================

if __name__ == "__main__":
    from chatbot import build_chatbot

    print("Building chatbot...")
    bot = build_chatbot()

    # Run evaluation
    results = run_evaluation(bot)

    # Print summary
    print_evaluation_summary(results)

    # Save to history
    save_evaluation_history(results, model_name="claude-haiku-4-5-20251001")
    save_evaluation_cases(results, model_name="claude-haiku-4-5-20251001")
