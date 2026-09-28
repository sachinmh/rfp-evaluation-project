-- RFP Evaluation and Supplier Ranking: SQLite schema

CREATE TABLE IF NOT EXISTS evaluation_criteria (
    criterion_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    description    TEXT,
    weight         REAL NOT NULL,     -- percentage, e.g. 30 means 30%
    max_score      REAL NOT NULL DEFAULT 10,
    is_active      INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS rfp_runs (
    rfp_run_id     TEXT PRIMARY KEY,
    created_at     TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'pending'   -- pending | completed | failed
);

CREATE TABLE IF NOT EXISTS supplier_results (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    rfp_run_id         TEXT NOT NULL,
    supplier_name      TEXT NOT NULL,
    submission_date    TEXT NOT NULL,
    experience_rating  REAL NOT NULL,
    absolute_score     REAL NOT NULL,
    ppi                REAL NOT NULL,
    final_rank         INTEGER NOT NULL,
    result_json        TEXT NOT NULL,
    FOREIGN KEY (rfp_run_id) REFERENCES rfp_runs(rfp_run_id)
);

-- Normalized per-criterion breakdown, used by the detailed scorecard screen
CREATE TABLE IF NOT EXISTS supplier_criterion_scores (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    rfp_run_id             TEXT NOT NULL,
    supplier_name          TEXT NOT NULL,
    criterion_id           INTEGER NOT NULL,
    criterion_name         TEXT NOT NULL,
    weight                 REAL NOT NULL,
    raw_score              REAL NOT NULL,
    max_score              REAL NOT NULL,
    weighted_contribution  REAL NOT NULL,
    benchmark_score        REAL NOT NULL,
    gap                    REAL NOT NULL,
    relative_pct           REAL NOT NULL,
    justification          TEXT,
    evidence               TEXT,
    was_normalized         INTEGER NOT NULL DEFAULT 0,
    normalization_note     TEXT,
    FOREIGN KEY (rfp_run_id) REFERENCES rfp_runs(rfp_run_id)
);

CREATE TABLE IF NOT EXISTS run_warnings (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    rfp_run_id     TEXT NOT NULL,
    supplier_name  TEXT,
    warning_text   TEXT NOT NULL,
    FOREIGN KEY (rfp_run_id) REFERENCES rfp_runs(rfp_run_id)
);

CREATE INDEX IF NOT EXISTS idx_supplier_results_run ON supplier_results(rfp_run_id);
CREATE INDEX IF NOT EXISTS idx_criterion_scores_run ON supplier_criterion_scores(rfp_run_id);
CREATE INDEX IF NOT EXISTS idx_warnings_run ON run_warnings(rfp_run_id);
