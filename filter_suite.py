#!/usr/bin/env python
"""
filter_suite.py - Incremental filter testing suite

Tests different combinations of Math/Stats + Calendar pages
and records evaluation results.

Usage:
    python filter_suite.py
"""

import json
import os
import subprocess
import sys


def combine_json_files(files, output):
    """Combine multiple JSON files into one."""
    combined = []
    for f in files:
        if os.path.exists(f):
            with open(f) as fp:
                data = json.load(fp)
                combined.extend(data if isinstance(data, list) else [data])

    with open(output, "w") as fp:
        json.dump(combined, fp, indent=2)

    return len(combined)


def run_make_db(input_file, verbose=False):
    """Build the vector database."""
    cmd = [sys.executable, "make_db.py", "--input", input_file]
    if verbose:
        cmd.append("-v")

    result = subprocess.run(["rm", "-rf", "db/"], capture_output=True)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


def run_evaluation():
    """Run evaluation and extract scores."""
    result = subprocess.run(
        [sys.executable, "evaluation.py"], capture_output=True, text=True, timeout=300
    )

    if result.returncode != 0:
        return None

    output = result.stdout

    # Extract metrics
    metrics = {}
    for line in output.split("\n"):
        if "Retrieval Precision" in line:
            metrics["precision"] = float(line.split(":")[1].strip())
        elif "Keyword Coverage" in line:
            metrics["keywords"] = float(line.split(":")[1].strip())
        elif "ROUGE-L" in line:
            metrics["rouge"] = float(line.split(":")[1].strip())
        elif "Overall Score" in line:
            metrics["overall"] = float(line.split(":")[1].strip())

    return metrics


def filter_math_stats(output_file):
    """Filter all Math & Stats department pages (ALL 87)."""
    print("Filtering ALL Math & Stats department pages...")

    # Get all URLs from manifest
    with open("tmp/raw_html/manifest.json") as f:
        manifest = json.load(f)

    print(f"Total URLs in manifest: {len(manifest)}")

    # Parse ALL URLs (not just priority filtered)
    from parsers import parse_html_to_sections

    results = []
    for i, entry in enumerate(manifest, 1):
        url = entry.get("url", "")
        filename = entry.get("file", "")

        filepath = f"tmp/raw_html/{filename}"
        if os.path.exists(filepath):
            with open(filepath) as f:
                html = f.read()
            result = parse_html_to_sections(html, url)
            results.append(result)
            if i % 20 == 0 or i == len(manifest):
                print(f"[{i}/{len(manifest)}] Parsed: {url[:50]}...")

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    return len(results)


def filter_calendar(output_file, max_urls, input_dir="tmp/raw_html_calendar"):
    """Filter calendar pages with MATH/STAT content."""
    print(f"Filtering calendar ({max_urls} max)...")

    from filter_crawler import score_url, is_calendar_math_stat

    with open(f"{input_dir}/manifest.json") as f:
        manifest = json.load(f)

    # Find calendar URLs
    calendar_urls = []
    for entry in manifest:
        url = entry.get("url", "")
        if "calendar" in url:
            calendar_urls.append((url, entry.get("file")))

    # Check content and filter
    filtered = []
    for url, filename in calendar_urls[
        : max_urls * 3
    ]:  # Check more in case some fail content
        filepath = f"{input_dir}/{filename}"
        if os.path.exists(filepath) and is_calendar_math_stat(filepath):
            filtered.append((url, filename))
            if len(filtered) >= max_urls:
                break

    # Parse
    from parsers import parse_html_to_sections

    results = []
    for i, (url, filename) in enumerate(filtered, 1):
        filepath = f"{input_dir}/{filename}"
        with open(filepath) as f:
            html = f.read()
        result = parse_html_to_sections(html, url)
        results.append(result)
        print(f"[{i}/{len(filtered)}] Parsed: {url[:50]}...")

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    return len(results)


def main():
    results_file = "data/filter_suite_results.json"

    all_results = []

    # Test 1: All Math & Stats only
    print("\n" + "=" * 50)
    print("TEST 1: All Math & Stats (87 pages)")
    print("=" * 50)

    math_count = filter_math_stats("data/pages_math.json")
    combine_json_files(["data/pages_math.json"], "data/pages_filtered.json")
    run_make_db("data/pages_filtered.json")
    metrics = run_evaluation()

    test_result = {
        "test": "Math & Stats only",
        "math_pages": math_count,
        "calendar_pages": 0,
        "total_pages": math_count,
    }
    if metrics:
        test_result.update(metrics)
    all_results.append(test_result)

    print(f"\nResults: {metrics}")

    # Test 2: + 10 calendar pages
    print("\n" + "=" * 50)
    print("TEST 2: + 10 Calendar pages")
    print("=" * 50)

    cal_count = filter_calendar("data/pages_calendar.json", 10)
    total = combine_json_files(
        ["data/pages_math.json", "data/pages_calendar.json"], "data/pages_filtered.json"
    )
    run_make_db("data/pages_filtered.json")
    metrics = run_evaluation()

    test_result = {
        "test": "+ 10 Calendar",
        "math_pages": math_count,
        "calendar_pages": cal_count,
        "total_pages": total,
    }
    if metrics:
        test_result.update(metrics)
    all_results.append(test_result)

    print(f"\nResults: {metrics}")

    # Test 3: + 20 calendar pages
    print("\n" + "=" * 50)
    print("TEST 3: + 20 Calendar pages")
    print("=" * 50)

    cal_count = filter_calendar("data/pages_calendar.json", 20)
    total = combine_json_files(
        ["data/pages_math.json", "data/pages_calendar.json"], "data/pages_filtered.json"
    )
    run_make_db("data/pages_filtered.json")
    metrics = run_evaluation()

    test_result = {
        "test": "+ 20 Calendar",
        "math_pages": math_count,
        "calendar_pages": cal_count,
        "total_pages": total,
    }
    if metrics:
        test_result.update(metrics)
    all_results.append(test_result)

    print(f"\nResults: {metrics}")

    # Test 4: + 50 calendar pages
    print("\n" + "=" * 50)
    print("TEST 4: + 50 Calendar pages")
    print("=" * 50)

    cal_count = filter_calendar("data/pages_calendar.json", 50)
    total = combine_json_files(
        ["data/pages_math.json", "data/pages_calendar.json"], "data/pages_filtered.json"
    )
    run_make_db("data/pages_filtered.json")
    metrics = run_evaluation()

    test_result = {
        "test": "+ 50 Calendar",
        "math_pages": math_count,
        "calendar_pages": cal_count,
        "total_pages": total,
    }
    if metrics:
        test_result.update(metrics)
    all_results.append(test_result)

    print(f"\nResults: {metrics}")

    # Save results
    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2)

    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    for r in all_results:
        print(
            f"{r['test']}: Overall={r.get('overall', 'N/A'):.3f}, Keywords={r.get('keywords', 'N/A'):.3f}"
        )


if __name__ == "__main__":
    main()
