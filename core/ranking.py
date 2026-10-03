"""
Ranking Tool: pure, deterministic Python. No LLM calls happen here.

Given normalized per-criterion scores for every supplier in a batch, this module computes:
  - absolute weighted score per supplier
  - per-criterion benchmark (best score observed across the batch)
  - per-criterion gap and relative performance %
  - Peer Performance Index (PPI)
  - final rank, using the mandatory tie-break order

Same inputs always produce the same outputs (Success condition in the project brief).
"""
from __future__ import annotations

from typing import Any


def compute_weighted_contributions(criteria_scores: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Adds 'weighted_contribution' = (raw_score / max_score) * weight to each criterion dict."""
    out = []
    for c in criteria_scores:
        contribution = (c["raw_score"] / c["max_score"]) * c["weight"] if c["max_score"] else 0.0
        out.append({**c, "weighted_contribution": contribution})
    return out


def compute_absolute_score(criteria_scores: list[dict[str, Any]]) -> float:
    return round(sum(c["weighted_contribution"] for c in criteria_scores), 4)


def compute_benchmarks(all_suppliers_criteria: dict[str, list[dict[str, Any]]]) -> dict[int, float]:
    """Highest valid raw_score observed for each criterion_id, across all suppliers in the run."""
    benchmarks: dict[int, float] = {}
    for criteria_scores in all_suppliers_criteria.values():
        for c in criteria_scores:
            cid = c["criterion_id"]
            benchmarks[cid] = max(benchmarks.get(cid, float("-inf")), c["raw_score"])
    return {cid: (v if v != float("-inf") else 0.0) for cid, v in benchmarks.items()}


def apply_benchmarks(criteria_scores: list[dict[str, Any]], benchmarks: dict[int, float]) -> list[dict[str, Any]]:
    """Adds benchmark_score, gap, and relative_pct to each criterion dict.

    Safe handling when benchmark is 0: every supplier's raw_score must also be 0 in that case
    (0 is the max possible), so they are treated as tied at 100% relative performance rather
    than triggering a division by zero.
    """
    out = []
    for c in criteria_scores:
        benchmark = benchmarks.get(c["criterion_id"], 0.0)
        gap = round(c["raw_score"] - benchmark, 4)
        if benchmark == 0:
            relative_pct = 100.0
        else:
            relative_pct = round((c["raw_score"] / benchmark) * 100, 4)
        out.append({**c, "benchmark_score": benchmark, "gap": gap, "relative_pct": relative_pct})
    return out


def compute_ppi(criteria_scores: list[dict[str, Any]]) -> float:
    """Weighted average of each criterion's relative-performance percentage."""
    total_weight = sum(c["weight"] for c in criteria_scores) or 1.0
    weighted_sum = sum(c["relative_pct"] * c["weight"] for c in criteria_scores)
    return round(weighted_sum / total_weight, 4)


def rank_suppliers(suppliers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Sorts suppliers by the mandatory tie-break order and assigns final_rank 1..n:
      1) Higher PPI first
      2) Earlier submission date
      3) Higher historical experience rating
      4) Supplier name, ascending

    `suppliers` items must have: ppi, submission_date (ISO 'YYYY-MM-DD' string),
    experience_rating, supplier_name.
    """

    def sort_key(s: dict[str, Any]):
        return (
            -s["ppi"],
            s["submission_date"],
            -s["experience_rating"],
            s["supplier_name"].lower(),
        )

    ordered = sorted(suppliers, key=sort_key)
    for rank, supplier in enumerate(ordered, start=1):
        supplier["final_rank"] = rank
    return ordered


def tie_break_explanation() -> str:
    return (
        "Suppliers are ranked by: (1) higher Peer Performance Index (PPI) first, "
        "(2) earlier submission date as the first tie-break, "
        "(3) higher historical experience rating as the second tie-break, "
        "(4) supplier name in ascending alphabetical order as the final tie-break. "
        "Ranks are assigned sequentially (1, 2, 3, ...) after this stable sort."
    )
