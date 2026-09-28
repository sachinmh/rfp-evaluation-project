"""
Seeds ONE demo run into the app's actual database (db/rfp_evaluation.db) using a
FakeLLMClient, purely so the Streamlit screens have real data to screenshot/demo
without needing a live API key. Safe to delete afterwards by re-running db/init_db.py
on a fresh db file, or just leave it as your required "successful run + validation
warning" demonstration.

Run: python scripts/seed_demo_run.py
"""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from db.init_db import DB_PATH, init_db  # noqa: E402
from scripts.smoke_test import FakeLLMClient, SAMPLE_DIR  # noqa: E402
from src import database as db  # noqa: E402
from src.orchestrator import SupplierInput, run_batch_evaluation  # noqa: E402


def main():
    init_db(DB_PATH)
    conn = db.get_connection(DB_PATH)
    active_criteria = db.get_active_criteria(conn)

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

    result = run_batch_evaluation(conn, FakeLLMClient(), active_criteria, supplier_inputs)
    conn.close()
    print(f"Demo run seeded into {DB_PATH}")
    print(f"RFP_RUN_ID: {result['rfp_run_id']}")
    print(f"Warnings: {len(result['warnings'])}")


if __name__ == "__main__":
    main()
