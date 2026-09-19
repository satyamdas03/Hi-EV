"""Standalone eval report runner for the Hi-EV Phase B harness.

Usage:
    python scripts/run_eval.py

Runs `pytest tests/eval/ -v`, parses per-case scores printed by the eval
tests, and prints + writes a JSON score report.
"""

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPORT_PATH = Path("eval_report.json")
SCORE_LINE_RE = re.compile(
    r"\[(?P<category>[\w-]+)\]\s+score=(?P<score>[\d.]+)\s+latency=(?P<latency>\d+)ms\s+\|\s+(?P<query>.+)"
)


def run_pytest() -> tuple[int, str, str]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/eval/",
        "-v",
        "-s",
        "-p",
        "no:cacheprovider",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout, result.stderr


def parse_results(stdout: str) -> list[dict]:
    results = []
    for line in stdout.splitlines():
        match = SCORE_LINE_RE.search(line)
        if not match:
            continue
        results.append(
            {
                "category": match.group("category"),
                "score": float(match.group("score")),
                "latency_ms": int(match.group("latency")),
                "query": match.group("query").strip(),
            }
        )
    return results


def summarize(results: list[dict]) -> dict:
    by_category: dict[str, list[float]] = defaultdict(list)
    latencies_by_category: dict[str, list[int]] = defaultdict(list)
    for r in results:
        by_category[r["category"]].append(r["score"])
        latencies_by_category[r["category"]].append(r["latency_ms"])

    category_scores = {}
    for category, scores in by_category.items():
        category_scores[category] = {
            "count": len(scores),
            "avg_score": round(sum(scores) / len(scores), 4),
            "min_score": round(min(scores), 4),
            "max_score": round(max(scores), 4),
            "avg_latency_ms": int(sum(latencies_by_category[category]) / len(scores)),
        }

    all_scores = [r["score"] for r in results]
    overall_avg = round(sum(all_scores) / len(all_scores), 4) if all_scores else 0.0
    return {
        "total_cases": len(results),
        "overall_avg_score": overall_avg,
        "categories": category_scores,
        "cases": results,
    }


def main() -> int:
    print("Running Hi-EV eval harness...")
    returncode, stdout, stderr = run_pytest()

    results = parse_results(stdout)
    if not results:
        print("No eval results found in pytest output.")
        print("stdout:", stdout[-2000:])
        print("stderr:", stderr[-2000:])
        return 1

    report = summarize(results)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n=== Hi-EV Eval Report ===")
    print(f"Total cases: {report['total_cases']}")
    print(f"Overall avg score: {report['overall_avg_score']:.2f}")
    print("\nPer-category:")
    for category, stats in sorted(report["categories"].items()):
        print(
            f"  {category:12s}  count={stats['count']:3d}  "
            f"avg={stats['avg_score']:.2f}  min={stats['min_score']:.2f}  "
            f"max={stats['max_score']:.2f}  latency={stats['avg_latency_ms']}ms"
        )
    print(f"\nReport written to {REPORT_PATH.resolve()}")

    return 0 if returncode == 0 else returncode


if __name__ == "__main__":
    sys.exit(main())
