"""
Orchestrator Agent: controls the workflow and calls each tool in the required order.

Setup -> Input (handled by Streamlit) -> Batch -> Evaluate -> Validate -> Score ->
Benchmark -> Rank -> Persist -> Present (handled by Streamlit).

The LLM is only ever asked to judge proposal content (core/evaluator.py). Every arithmetic,
benchmarking, tie-break, and ranking decision happens in core/ranking.py, which never calls
the LLM.
"""
from __future__ import annotations

import uuid
from typing import Any

from core import database as db
from core.evaluator import evaluate_supplier
from core.llm_client import LLMClient
from core.pdf_tool import extract_text
from core.ranking import (
    apply_benchmarks,
    compute_absolute_score,
    compute_benchmarks,
    compute_ppi,
    compute_weighted_contributions,
    rank_suppliers,
)
from core.validation import normalize_llm_output


class SupplierInput:
    def __init__(self, supplier_name: str, submission_date: str, experience_rating: float, pdf_bytes: bytes):
        self.supplier_name = supplier_name
        self.submission_date = submission_date  # ISO 'YYYY-MM-DD'
        self.experience_rating = experience_rating
        self.pdf_bytes = pdf_bytes


def run_batch_evaluation(
    conn,
    llm_client: LLMClient,
    active_criteria: list[dict[str, Any]],
    supplier_inputs: list[SupplierInput],
) -> dict[str, Any]:
    """Runs the full pipeline for one batch of suppliers and persists the result.

    Returns a dict with rfp_run_id, suppliers (ranked, with full breakdown), and warnings.
    """
    rfp_run_id = str(uuid.uuid4())
    db.create_run(conn, rfp_run_id)

    try:
        return _run_batch_evaluation_inner(conn, llm_client, active_criteria, supplier_inputs, rfp_run_id)
    except Exception:
        # Leave no dangling 'pending' run behind — mark it failed so it's excluded from
        # the run selector instead of showing up as a leaderboard with zero suppliers.
        db.set_run_status(conn, rfp_run_id, "failed")
        raise


def _run_batch_evaluation_inner(
    conn,
    llm_client: LLMClient,
    active_criteria: list[dict[str, Any]],
    supplier_inputs: list[SupplierInput],
    rfp_run_id: str,
) -> dict[str, Any]:
    all_warnings: list[dict[str, str]] = []
    per_supplier_criteria: dict[str, list[dict[str, Any]]] = {}
    supplier_meta: dict[str, dict[str, Any]] = {}

    # Evaluate + Validate + Score (per supplier)
    for supplier in supplier_inputs:
        document_text = extract_text(supplier.pdf_bytes)

        raw_response = evaluate_supplier(
            llm_client=llm_client,
            criteria=active_criteria,
            supplier_name=supplier.supplier_name,
            document_text=document_text,
        )

        normalized, warnings = normalize_llm_output(
            raw_text=raw_response,
            active_criteria=active_criteria,
            supplier_name=supplier.supplier_name,
        )
        for w in warnings:
            all_warnings.append({"supplier_name": supplier.supplier_name, "message": w})

        scored = compute_weighted_contributions(normalized)
        per_supplier_criteria[supplier.supplier_name] = scored
        supplier_meta[supplier.supplier_name] = {
            "submission_date": supplier.submission_date,
            "experience_rating": supplier.experience_rating,
        }

    # Benchmark (across the whole batch)
    benchmarks = compute_benchmarks(per_supplier_criteria)

    # Apply benchmarks + compute PPI + absolute score per supplier
    supplier_results: list[dict[str, Any]] = []
    for supplier_name, criteria_scores in per_supplier_criteria.items():
        criteria_with_benchmarks = apply_benchmarks(criteria_scores, benchmarks)
        absolute_score = compute_absolute_score(criteria_with_benchmarks)
        ppi = compute_ppi(criteria_with_benchmarks)

        supplier_results.append(
            {
                "supplier_name": supplier_name,
                "submission_date": supplier_meta[supplier_name]["submission_date"],
                "experience_rating": supplier_meta[supplier_name]["experience_rating"],
                "absolute_score": absolute_score,
                "ppi": ppi,
                "criteria": criteria_with_benchmarks,
            }
        )

    # Rank (deterministic tie-break order)
    ranked = rank_suppliers(supplier_results)

    # Persist
    for supplier in ranked:
        db.save_supplier_result(conn, rfp_run_id, supplier)
    db.save_warnings(conn, rfp_run_id, all_warnings)
    db.set_run_status(conn, rfp_run_id, "completed")

    return {"rfp_run_id": rfp_run_id, "suppliers": ranked, "warnings": all_warnings}
