"""Database access layer (SQLite). No business logic lives here."""
import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any

from db.init_db import DB_PATH, get_connection, init_db


def ensure_db_ready(db_path: str = DB_PATH) -> None:
    if not os.path.exists(db_path):
        init_db(db_path)
    else:
        # make sure tables exist even if the file was created empty
        init_db(db_path)


def get_active_criteria(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT criterion_id, name, description, weight, max_score, is_active
           FROM evaluation_criteria WHERE is_active = 1 ORDER BY criterion_id"""
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_criteria(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT criterion_id, name, description, weight, max_score, is_active
           FROM evaluation_criteria ORDER BY criterion_id"""
    ).fetchall()
    return [dict(r) for r in rows]


def create_run(conn: sqlite3.Connection, rfp_run_id: str) -> None:
    conn.execute(
        "INSERT INTO rfp_runs (rfp_run_id, created_at, status) VALUES (?, ?, ?)",
        (rfp_run_id, datetime.now(timezone.utc).isoformat(), "pending"),
    )
    conn.commit()


def set_run_status(conn: sqlite3.Connection, rfp_run_id: str, status: str) -> None:
    conn.execute("UPDATE rfp_runs SET status = ? WHERE rfp_run_id = ?", (status, rfp_run_id))
    conn.commit()


def save_supplier_result(conn: sqlite3.Connection, rfp_run_id: str, supplier: dict[str, Any]) -> None:
    conn.execute(
        """INSERT INTO supplier_results
           (rfp_run_id, supplier_name, submission_date, experience_rating,
            absolute_score, ppi, final_rank, result_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            rfp_run_id,
            supplier["supplier_name"],
            supplier["submission_date"],
            supplier["experience_rating"],
            supplier["absolute_score"],
            supplier["ppi"],
            supplier["final_rank"],
            json.dumps(supplier),
        ),
    )
    for c in supplier["criteria"]:
        conn.execute(
            """INSERT INTO supplier_criterion_scores
               (rfp_run_id, supplier_name, criterion_id, criterion_name, weight,
                raw_score, max_score, weighted_contribution, benchmark_score,
                gap, relative_pct, justification, evidence, was_normalized, normalization_note)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                rfp_run_id,
                supplier["supplier_name"],
                c["criterion_id"],
                c["criterion_name"],
                c["weight"],
                c["raw_score"],
                c["max_score"],
                c["weighted_contribution"],
                c["benchmark_score"],
                c["gap"],
                c["relative_pct"],
                c.get("justification", ""),
                c.get("evidence", ""),
                int(c.get("was_normalized", False)),
                c.get("normalization_note", ""),
            ),
        )
    conn.commit()


def save_warnings(conn: sqlite3.Connection, rfp_run_id: str, warnings: list[dict[str, str]]) -> None:
    for w in warnings:
        conn.execute(
            "INSERT INTO run_warnings (rfp_run_id, supplier_name, warning_text) VALUES (?, ?, ?)",
            (rfp_run_id, w.get("supplier_name"), w["message"]),
        )
    conn.commit()


def list_runs(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT rfp_run_id, created_at, status FROM rfp_runs ORDER BY created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_run_results(conn: sqlite3.Connection, rfp_run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT * FROM supplier_results WHERE rfp_run_id = ? ORDER BY final_rank""",
        (rfp_run_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_run_warnings(conn: sqlite3.Connection, rfp_run_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT supplier_name, warning_text FROM run_warnings WHERE rfp_run_id = ?",
        (rfp_run_id,),
    ).fetchall()
    return [dict(r) for r in rows]
