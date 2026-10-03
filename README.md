# Agentic RFP Evaluation and Supplier Ranking

An AI-assisted Streamlit application that reads supplier RFP PDFs, scores them against
configurable criteria using an LLM, then applies **deterministic Python** to benchmark,
rank, and tie-break suppliers into an explainable leaderboard.

> **Design principle:** the LLM only judges proposal *content* (per-criterion score +
> justification + evidence). It never computes weighted totals, benchmarks, tie-breaks,
> or final rank — that logic lives entirely in `core/ranking.py` and is provider-independent,
> so the same inputs always produce the same leaderboard.

## 1. Architecture

```
Streamlit UI (app.py)
   │
   ▼
Orchestrator Agent (core/orchestrator.py)
   │
   ├─► Document Tool (core/pdf_tool.py)        — pypdf text extraction
   ├─► Evaluation Agent (core/evaluator.py)     — builds grounded prompt
   │        └─► LLM Client (core/llm_client.py) — Anthropic or OpenAI, JSON output
   ├─► Validation Tool (core/validation.py)     — Pydantic schema check + normalization
   └─► Ranking Tool (core/ranking.py)           — scoring, benchmarks, PPI, tie-break, rank
   │
   ▼
SQLite (db/schema.sql via core/database.py)
```

| Component | File | Responsibility |
|---|---|---|
| Orchestrator Agent | `core/orchestrator.py` | Runs the pipeline in the required order for one batch |
| Document Tool | `core/pdf_tool.py` | Extracts clean text from each uploaded PDF (`pypdf`) |
| Evaluation Agent | `core/evaluator.py` | Builds the evidence-grounded prompt; calls the LLM per supplier |
| LLM Client | `core/llm_client.py` | Provider-agnostic wrapper — Anthropic, OpenAI, **or OpenRouter**, selectable in the sidebar |
| Validation Tool | `core/validation.py` | Parses/validates LLM JSON with Pydantic; fills missing criteria, clips out-of-range scores, records warnings |
| Ranking Tool | `core/ranking.py` | Pure deterministic Python: weighted score, benchmark, gap, relative %, PPI, tie-break sort, rank |
| Database layer | `core/database.py`, `db/init_db.py`, `db/schema.sql` | SQLite persistence |

## 2. Data flow

Setup → Input → Batch → Evaluate → Validate → Score → Benchmark → Rank → Persist → Present
(matches the 10-step flow in the project brief). Every run is tagged with one `rfp_run_id`
(UUID4), used to group `supplier_results` and `supplier_criterion_scores` rows.

## 3. Formulas

| Metric | Formula |
|---|---|
| Absolute weighted score | `Σ (raw_score / max_score) × weight` across all active criteria (weight in %, so this lands on a 0-100 scale) |
| Criterion benchmark | `max(raw_score)` for that criterion across all suppliers in the batch |
| Criterion gap | `raw_score − benchmark` (0 for the benchmark leader, otherwise ≤ 0) |
| Relative performance % | `(raw_score / benchmark) × 100` |
| Peer Performance Index (PPI) | Weighted average of each criterion's relative % (weights = criterion weights) |

**Assumption — benchmark of 0:** if every supplier scores 0 on a criterion, the benchmark is
0 and a literal division would be undefined. We treat that case as *all suppliers tied at
100% relative performance* on that criterion, since 0 is also the maximum observed — this is
implemented explicitly in `core/ranking.py:apply_benchmarks`.

### Mandatory tie-break order (`core/ranking.py:rank_suppliers`)
1. Higher PPI first
2. Earlier submission date
3. Higher historical experience rating
4. Supplier name, ascending

Rank is assigned sequentially (1, 2, 3, ...) after this single stable sort, so ties cascade
correctly through all four keys at once.

## 4. Validation & normalization rules

Implemented in `core/validation.py`, applied before any scoring happens:
- Strips markdown code fences if the model wraps JSON despite instructions.
- Unparsable JSON → every criterion for that supplier defaults to score 0, with a warning.
- Criterion missing from the LLM response → defaulted to score 0, with a warning.
- Score below 0 or above the criterion's configured `max_score` → clipped, with a warning.
- Criterion IDs returned by the LLM that aren't in the active set → ignored, with a warning.

All warnings are shown in the **Run Details** screen and persisted in `run_warnings`, so every
correction is traceable.

## 5. Database schema (`db/schema.sql`)

- `evaluation_criteria` — criterion_id, name, description, weight, max_score, is_active
- `rfp_runs` — rfp_run_id, created_at, status
- `supplier_results` — one row per supplier per run (absolute_score, ppi, final_rank, full `result_json`)
- `supplier_criterion_scores` — per-criterion breakdown (benchmark, gap, relative %, evidence, normalization flags) for the detailed scorecard screen
- `run_warnings` — every validation warning, linked to the run and supplier

## 6. Setup (local)

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python db/init_db.py                    # creates + seeds db/rfp_evaluation.db
python scripts/generate_sample_pdfs.py  # regenerates the 4 sample supplier PDFs (already included)

cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit .streamlit/secrets.toml and paste whichever key(s) you'll use:
# ANTHROPIC_API_KEY, OPENAI_API_KEY, and/or OPENROUTER_API_KEY

streamlit run app.py
```

In the app sidebar, pick **anthropic**, **openai**, or **openrouter**, confirm/override the
API key and model, then go to **Supplier Input**, upload the 4 PDFs from
`data/sample_pdfs/`, fill in each supplier's name / submission date / experience rating,
and click **Evaluate Batch**.

**Using OpenRouter:** OpenRouter exposes an OpenAI-compatible API, so `core/llm_client.py`
talks to it via the `openai` SDK pointed at `https://openrouter.ai/api/v1`. Get a key from
[openrouter.ai/keys](https://openrouter.ai/keys), select **openrouter** in the sidebar, and
set the model field to an OpenRouter model slug, e.g. `anthropic/claude-sonnet-5`,
`openai/gpt-4o-mini`, or `meta-llama/llama-3.1-70b-instruct`. Strict JSON mode isn't forced
for this provider since not every model routed through OpenRouter supports it — the
Validation Tool already tolerates loosely-formatted JSON (stripped code fences, etc.).

## 7. Testing / reproducibility

`scripts/smoke_test.py` runs the entire pipeline (extraction → evaluation → validation →
scoring → ranking → persistence) against the 4 sample PDFs using a `FakeLLMClient` — **no
API key or network call required**. It deliberately injects a missing criterion and an
out-of-range score to exercise the Validation Tool's normalization path, then asserts:
- ranks are sequential,
- the tie-break order is respected between every adjacent pair,
- every score and benchmark stays within its valid range,
- persisted rows match what was computed.

```bash
python scripts/smoke_test.py
```

This also regenerates `exports/sample_run.json` — a sample completed-run export in the exact
shape the app's **Run Details → Download JSON** button produces. Replace it with a real run's
export once you've evaluated the sample PDFs with a live LLM.

## 8. Deploying to Streamlit Community Cloud

1. Push this repo to GitHub (public, or private if your Streamlit account is linked to it).
2. Go to [share.streamlit.io](https://share.streamlit.io) → sign in with GitHub → **New app**.
3. Select this repo, the branch, and `app.py` as the entry point.
4. Under **Advanced settings → Secrets**, paste:
   ```toml
   ANTHROPIC_API_KEY = "sk-ant-..."
   OPENAI_API_KEY = "sk-..."
   ```
5. Deploy. You'll get a public URL like `https://<app-name>.streamlit.app`.

**Note on persistence:** Streamlit Community Cloud's filesystem is ephemeral — the SQLite
file resets on app restart/redeploy. This satisfies the classroom brief (which only requires
persistence *within* the app's runtime), but don't rely on it as permanent storage. For
durable storage across restarts, point `DB_PATH` at a mounted volume or an external database.

## 9. Project structure

```
rfp_evaluation_project/
├── app.py                       # Streamlit UI (5 screens)
├── requirements.txt
├── README.md
├── db/
│   ├── schema.sql
│   ├── init_db.py                # creation + seed script
│   └── rfp_evaluation.db         # generated, gitignored
├── core/
│   ├── database.py
│   ├── pdf_tool.py                # Document Tool
│   ├── llm_client.py               # provider-agnostic LLM wrapper
│   ├── evaluator.py                # Evaluation Agent (prompting)
│   ├── validation.py               # Validation Tool
│   ├── ranking.py                  # Ranking Tool (deterministic)
│   └── orchestrator.py             # Orchestrator Agent
├── scripts/
│   ├── generate_sample_pdfs.py    # builds the 4 synthetic supplier PDFs
│   └── smoke_test.py               # end-to-end test with a fake LLM
├── data/sample_pdfs/               # 4 synthetic supplier RFP PDFs
├── exports/sample_run.json         # sample completed-run export
└── screenshots/                    # add screenshots after running the app (see below)
```

## 10. Screenshots

Add screenshots of the running app here after a local or deployed run:
`screenshots/01_criteria.png`, `02_supplier_input.png`, `03_leaderboard.png`,
`04_scorecard.png`, `05_run_details.png`.

## 11. Synthetic supplier profiles

| Supplier | Profile |
|---|---|
| Apex Systems | Strong technical design and security; higher price; moderate delivery schedule |
| BrightPath Tech | Lowest price and fastest timeline; weak compliance detail; limited experience |
| NexaWorks | Balanced; strongest implementation plan and support model |
| Orbit Digital | Strong experience and references; vague integration plan; medium pricing |

All data is fictional, generated for this classroom exercise — no real supplier data is used.
