"""
Creates the SQLite database (if missing) and seeds default evaluation criteria.
Run directly:  python db/init_db.py
Safe to re-run: seeding is skipped if criteria already exist.
"""
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(__file__), "rfp_evaluation.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

DEFAULT_CRITERIA = [
    # name, description, weight, max_score, is_active
    ("Technical Capability", "Architecture, integrations, scalability, technical fit", 30, 10, 1),
    ("Implementation Plan", "Timeline, milestones, staffing, risk plan", 20, 10, 1),
    ("Commercial Value", "Pricing clarity, total cost, assumptions", 20, 10, 1),
    ("Security & Compliance", "Controls, certifications, privacy, auditability", 20, 10, 1),
    ("Support & Experience", "Support model, similar projects, references", 10, 10, 1),
]


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    with open(SCHEMA_PATH, "r") as f:
        schema = f.read()
    conn = get_connection(db_path)
    try:
        conn.executescript(schema)
        conn.commit()

        existing = conn.execute("SELECT COUNT(*) FROM evaluation_criteria").fetchone()[0]
        if existing == 0:
            conn.executemany(
                """INSERT INTO evaluation_criteria (name, description, weight, max_score, is_active)
                   VALUES (?, ?, ?, ?, ?)""",
                DEFAULT_CRITERIA,
            )
            conn.commit()
            print(f"Seeded {len(DEFAULT_CRITERIA)} default evaluation criteria.")
        else:
            print(f"evaluation_criteria already has {existing} row(s); skipped seeding.")
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Database ready at: {DB_PATH}")
