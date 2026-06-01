"""Evaluate retrieval quality against a curated question-to-clause dataset."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import requests


def normalize_clause_id(value: Any) -> str:
    return re.sub(r"_p\d+$", "", str(value or "").strip())


def evaluate_case(case: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    expected = {normalize_clause_id(item) for item in case.get("expected_clause_ids", []) if item}
    if not expected:
        raise ValueError(f"Question has no expected_clause_ids: {case.get('question')}")

    ranked_clause_ids = [
        normalize_clause_id((result.get("metadata") or {}).get("clause_id"))
        for result in results
    ]
    first_hit_rank = next(
        (rank for rank, clause_id in enumerate(ranked_clause_ids, start=1) if clause_id in expected),
        None,
    )
    return {
        "question": case["question"],
        "expected_clause_ids": sorted(expected),
        "ranked_clause_ids": ranked_clause_ids,
        "first_hit_rank": first_hit_rank,
        "hit": first_hit_rank is not None,
        "reciprocal_rank": 0.0 if first_hit_rank is None else 1.0 / first_hit_rank,
    }


def debug_search(base_url: str, question: str, top_k: int) -> list[dict[str, Any]]:
    response = requests.post(
        f"{base_url.rstrip('/')}/api/rag/debug/search",
        json={"question": question, "topK": top_k},
        timeout=90,
    )
    response.raise_for_status()
    return response.json().get("results") or []


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval Hit@K and MRR")
    parser.add_argument("dataset", type=Path, help="JSON file containing question and expected_clause_ids")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="RAG service URL")
    parser.add_argument("--top-k", type=int, default=10, help="Number of debug search results to inspect")
    args = parser.parse_args()

    cases = json.loads(args.dataset.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("Dataset must be a non-empty JSON array")

    reports = [
        evaluate_case(case, debug_search(args.base_url, case["question"], args.top_k))
        for case in cases
    ]
    hits = sum(1 for report in reports if report["hit"])
    mrr = sum(report["reciprocal_rank"] for report in reports) / len(reports)

    print(f"questions={len(reports)}")
    print(f"hit@{args.top_k}={hits / len(reports):.4f}")
    print(f"mrr@{args.top_k}={mrr:.4f}")
    for report in reports:
        status = "HIT" if report["hit"] else "MISS"
        print(f"[{status}] rank={report['first_hit_rank']} question={report['question']}")
        if not report["hit"]:
            print(f"  expected={report['expected_clause_ids']}")
            print(f"  actual={report['ranked_clause_ids']}")


if __name__ == "__main__":
    main()
