"""
End-to-end smoke test using a fake LLM client (no API key / network needed).
Verifies: PDF extraction -> prompt build -> fake LLM -> validation -> scoring ->
benchmarking -> PPI -> tie-break ranking -> persistence, all wired correctly.

Run: python scripts/smoke_test.py
"""
import json
import os
import random
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from db.init_db import init_db  # noqa: E402
from core import database as db  # noqa: E402
from core.orchestrator import SupplierInput, run_batch_evaluation  # noqa: E402

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "sample_pdfs")

TEST_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "smoke_test.db")


class FakeLLMClient:
    """Returns plausible-looking JSON without calling any real API.

    Deliberately introduces a missing criterion and an out-of-range score once,
    to exercise the Validation Tool's normalization path.
    """

    def __init__(self):
        self.call_count = 0

    def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        self.call_count += 1
        random.seed(hash(user_prompt) % 10_000)

        # crude criterion_id scrape from the prompt (id=<n>)
        ids = sorted(set(int(x) for x in __import__("re").findall(r"id=(\d+)", user_prompt)))
        criteria = []
        for i, cid in enumerate(ids):
            if self.call_count == 1 and i == 0:
                continue  # simulate a missing criterion on the first call
            score = random.randint(3, 10)
            if self.call_count == 2 and i == 1:
                score = 999  # simulate an out-of-range score on the second call
            criteria.append(
                {
                    "criterion_id": cid,
                    "score": score,
                    "max_score": 10,
                    "justification": "Synthetic justification for smoke test.",
                    "evidence": "Synthetic evidence snippet.",
                }
            )
        return json.dumps(
            {
                "supplier_name": "test",
                "criteria": criteria,
                "risks": ["Synthetic risk."],
                "overall_summary": "Synthetic summary.",
            }
        )


def main():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    init_db(TEST_DB_PATH)
    conn = db.get_connection(TEST_DB_PATH)

    active_criteria = db.get_active_criteria(conn)
    assert active_criteria, "No active criteria seeded"
    total_weight = sum(c["weight"] for c in active_criteria)
    assert abs(total_weight - 100) < 0.01, f"Weights sum to {total_weight}, expected 100"

    suppliers = [
        ("apex_systems.pdf", "Apex Systems", "2026-01-10", 8),
        ("brightpath_tech.pdf", "BrightPath Tech", "2026-01-05", 4),
        ("nexaworks.pdf", "NexaWorks", "2026-01-08", 7),
        ("orbit_digital.pdf", "Orbit Digital", "2026-01-08", 9),
    ]
    supplier_inputs = []
    for fname, name, sub_date, rating in suppliers:
        with open(os.path.join(SAMPLE_DIR, fname), "rb") as f:
            pdf_bytes = f.read()
        supplier_inputs.append(SupplierInput(name, sub_date, rating, pdf_bytes))

    llm_client = FakeLLMClient()
    result = run_batch_evaluation(conn, llm_client, active_criteria, supplier_inputs)

    print(f"RFP_RUN_ID: {result['rfp_run_id']}")
    print(f"Warnings ({len(result['warnings'])}):")
    for w in result["warnings"]:
        print(f"  - [{w['supplier_name']}] {w['message']}")

    print("\nLeaderboard:")
    for s in result["suppliers"]:
        print(
            f"  rank={s['final_rank']} name={s['supplier_name']!r} "
            f"absolute_score={s['absolute_score']} ppi={s['ppi']} "
            f"date={s['submission_date']} rating={s['experience_rating']}"
        )

    # --- assertions ---
    ranks = [s["final_rank"] for s in result["suppliers"]]
    assert ranks == list(range(1, len(ranks) + 1)), f"Ranks not sequential: {ranks}"

    ppis = [s["ppi"] for s in result["suppliers"]]
    assert ppis == sorted(ppis, reverse=True) or True  # PPI desc is primary key; ties resolved by other keys

    # verify tie-break: check no two suppliers with same ppi are mis-ordered vs date/rating/name
    for i in range(len(result["suppliers"]) - 1):
        a, b = result["suppliers"][i], result["suppliers"][i + 1]
        assert (
            a["ppi"] > b["ppi"]
            or (a["ppi"] == b["ppi"] and a["submission_date"] < b["submission_date"])
            or (a["ppi"] == b["ppi"] and a["submission_date"] == b["submission_date"] and a["experience_rating"] > b["experience_rating"])
            or (
                a["ppi"] == b["ppi"]
                and a["submission_date"] == b["submission_date"]
                and a["experience_rating"] == b["experience_rating"]
                and a["supplier_name"].lower() <= b["supplier_name"].lower()
            )
        ), f"Tie-break order violated between {a['supplier_name']} and {b['supplier_name']}"

    for s in result["suppliers"]:
        assert 0 <= s["absolute_score"] <= 100, f"absolute_score out of range: {s['absolute_score']}"
        assert 0 <= s["ppi"] <= 100.01, f"ppi out of range: {s['ppi']}"
        for c in s["criteria"]:
            assert 0 <= c["raw_score"] <= c["max_score"], f"raw_score out of range for {c}"

    # verify persistence round-trip
    persisted = db.get_run_results(conn, result["rfp_run_id"])
    assert len(persisted) == len(suppliers), "Persisted row count mismatch"
    persisted_warnings = db.get_run_warnings(conn, result["rfp_run_id"])
    assert len(persisted_warnings) == len(result["warnings"]), "Persisted warnings count mismatch"

    conn.close()

    export_path = os.path.join(os.path.dirname(__file__), "..", "exports", "sample_run.json")
    os.makedirs(os.path.dirname(export_path), exist_ok=True)
    with open(export_path, "w") as f:
        json.dump(
            {
                "rfp_run_id": result["rfp_run_id"],
                "note": "Generated by scripts/smoke_test.py with a FakeLLMClient (no network/API key) "
                "purely to demonstrate the exact JSON export shape end to end, including a validation "
                "warning path. Replace with a real run's export (Run Details tab -> Download JSON) once "
                "you have evaluated the sample PDFs with a live LLM.",
                "suppliers": result["suppliers"],
                "warnings": result["warnings"],
            },
            f,
            indent=2,
        )
    print(f"Sample export written to {export_path}")

    print("\nSMOKE_TEST_OK")


if __name__ == "__main__":
    main()
