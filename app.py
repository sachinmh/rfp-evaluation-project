"""
Agentic RFP Evaluation and Supplier Ranking — Streamlit app.

Screens: Criteria | Supplier Input & Evaluate | Leaderboard | Detailed Scorecard | Run Details
"""
import json
import os

import pandas as pd
import streamlit as st

from src import database as db
from src.llm_client import get_llm_client
from src.orchestrator import SupplierInput, run_batch_evaluation
from src.ranking import tie_break_explanation

st.set_page_config(page_title="Agentic RFP Evaluation", layout="wide")

db.ensure_db_ready()


def get_conn():
    return db.get_connection()


def secret_or_env(key: str) -> str:
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, "")


# --------------------------------------------------------------------------------------
# Sidebar: LLM provider configuration
# --------------------------------------------------------------------------------------
st.sidebar.title("LLM configuration")
provider = st.sidebar.selectbox("Provider", ["anthropic", "openai", "openrouter"], index=0)
SECRET_KEY_NAMES = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}
MODEL_DEFAULTS = {
    "anthropic": "claude-sonnet-5",
    "openai": "gpt-4o-mini",
    "openrouter": "google/gemma-4-26b-a4b-it:free",
}
default_key = secret_or_env(SECRET_KEY_NAMES[provider])
api_key = st.sidebar.text_input(
    f"{provider.capitalize()} API key",
    value=default_key,
    type="password",
    help="Reads from Streamlit secrets / environment first; you can override here for this session.",
)
model = st.sidebar.text_input("Model", value=MODEL_DEFAULTS[provider])
if provider == "openrouter":
    st.sidebar.caption(
        "OpenRouter model names use the 'provider/model' format, e.g. "
        "`anthropic/claude-sonnet-5`, `openai/gpt-4o-mini`, `meta-llama/llama-3.1-70b-instruct`."
    )

st.sidebar.markdown("---")
st.sidebar.caption(
    "The LLM only scores proposal content. All arithmetic, benchmarking, tie-breaks, "
    "and ranking are computed deterministically in Python."
)

st.title("Agentic RFP Evaluation and Supplier Ranking")

tab_criteria, tab_input, tab_leaderboard, tab_scorecard, tab_run = st.tabs(
    ["Criteria", "Supplier Input", "Leaderboard", "Detailed Scorecard", "Run Details"]
)

# --------------------------------------------------------------------------------------
# Screen: Criteria
# --------------------------------------------------------------------------------------
with tab_criteria:
    st.header("Active Evaluation Criteria")
    conn = get_conn()
    criteria = db.get_active_criteria(conn)
    conn.close()

    if not criteria:
        st.warning("No active criteria found. Seed the database via `python db/init_db.py`.")
    else:
        df = pd.DataFrame(criteria)[["criterion_id", "name", "description", "weight", "max_score"]]
        df = df.rename(columns={"weight": "weight (%)"})
        st.dataframe(df, use_container_width=True, hide_index=True)
        total_weight = sum(c["weight"] for c in criteria)
        if abs(total_weight - 100) > 0.01:
            st.error(f"Active criteria weights sum to {total_weight}%, not 100%. Fix this in evaluation_criteria before running a batch.")
        else:
            st.success(f"Active criteria weights sum to {total_weight}%.")

# --------------------------------------------------------------------------------------
# Screen: Supplier Input & Evaluate
# --------------------------------------------------------------------------------------
with tab_input:
    st.header("Upload Supplier Proposals")

    conn = get_conn()
    active_criteria = db.get_active_criteria(conn)
    conn.close()

    uploaded_files = st.file_uploader(
        "Upload supplier RFP PDFs (multiple allowed)", type=["pdf"], accept_multiple_files=True
    )

    supplier_forms = []
    validation_messages = []

    if uploaded_files:
        st.subheader("Supplier metadata")
        for i, f in enumerate(uploaded_files):
            with st.expander(f"Metadata for: {f.name}", expanded=True):
                default_name = os.path.splitext(f.name)[0].replace("_", " ").title()
                name = st.text_input("Supplier name", value=default_name, key=f"name_{i}")
                sub_date = st.date_input("Submission date", key=f"date_{i}")
                rating = st.slider(
                    "Historical experience rating (1-10)", min_value=1, max_value=10, value=5, key=f"rating_{i}"
                )
                supplier_forms.append(
                    {"file": f, "name": name.strip(), "submission_date": sub_date, "experience_rating": rating}
                )

        names_seen = set()
        for sf in supplier_forms:
            if not sf["name"]:
                validation_messages.append(f"Supplier name is required for {sf['file'].name}.")
            elif sf["name"] in names_seen:
                validation_messages.append(f"Duplicate supplier name '{sf['name']}' — names must be unique within a batch.")
            names_seen.add(sf["name"])

        if not active_criteria:
            validation_messages.append("No active evaluation criteria configured — cannot evaluate.")
        elif abs(sum(c["weight"] for c in active_criteria) - 100) > 0.01:
            validation_messages.append("Active criteria weights do not sum to 100% — fix criteria before evaluating.")

        if not api_key:
            validation_messages.append(f"Enter your {provider.capitalize()} API key in the sidebar before evaluating.")

        for msg in validation_messages:
            st.warning(msg)

        evaluate_clicked = st.button("Evaluate Batch", type="primary", disabled=bool(validation_messages))

        if evaluate_clicked:
            with st.spinner("Extracting documents, calling the LLM, validating, scoring, and ranking..."):
                try:
                    llm_client = get_llm_client(provider, api_key, model)
                    supplier_inputs = [
                        SupplierInput(
                            supplier_name=sf["name"],
                            submission_date=sf["submission_date"].isoformat(),
                            experience_rating=float(sf["experience_rating"]),
                            pdf_bytes=sf["file"].getvalue(),
                        )
                        for sf in supplier_forms
                    ]
                    conn = get_conn()
                    active_criteria = db.get_active_criteria(conn)
                    result = run_batch_evaluation(conn, llm_client, active_criteria, supplier_inputs)
                    conn.close()
                    st.session_state["last_run"] = result
                    st.success(f"Batch evaluation complete. RFP_RUN_ID: {result['rfp_run_id']}")
                except Exception as exc:
                    st.error(f"Evaluation failed: {exc}")
    else:
        st.info("Upload at least one supplier PDF to begin. Sample PDFs are in data/sample_pdfs/.")

# --------------------------------------------------------------------------------------
# Shared run selector for the remaining screens
# --------------------------------------------------------------------------------------
conn = get_conn()
past_runs = db.list_runs(conn)
conn.close()

run_options = [r["rfp_run_id"] for r in past_runs]
default_run_id = st.session_state.get("last_run", {}).get("rfp_run_id")


def load_run(rfp_run_id: str):
    conn = get_conn()
    rows = db.get_run_results(conn, rfp_run_id)
    warnings = db.get_run_warnings(conn, rfp_run_id)
    conn.close()
    suppliers = [json.loads(r["result_json"]) for r in rows]
    suppliers.sort(key=lambda s: s["final_rank"])
    return suppliers, warnings


selected_run_id = None
if run_options:
    default_index = run_options.index(default_run_id) if default_run_id in run_options else 0
    selected_run_id = st.sidebar.selectbox("View run", run_options, index=default_index)
else:
    st.sidebar.caption("No completed runs yet.")

# --------------------------------------------------------------------------------------
# Screen: Leaderboard
# --------------------------------------------------------------------------------------
with tab_leaderboard:
    st.header("Leaderboard")
    if not selected_run_id:
        st.info("Run a batch evaluation first, or select a past run from the sidebar.")
    else:
        suppliers, warnings = load_run(selected_run_id)
        board_df = pd.DataFrame(
            [
                {
                    "Rank": s["final_rank"],
                    "Supplier": s["supplier_name"],
                    "Absolute Score": round(s["absolute_score"], 2),
                    "PPI": round(s["ppi"], 2),
                    "Submission Date": s["submission_date"],
                    "Experience Rating": s["experience_rating"],
                }
                for s in suppliers
            ]
        )
        st.dataframe(board_df, use_container_width=True, hide_index=True)
        st.bar_chart(board_df.set_index("Supplier")[["Absolute Score", "PPI"]])

# --------------------------------------------------------------------------------------
# Screen: Detailed Scorecard
# --------------------------------------------------------------------------------------
with tab_scorecard:
    st.header("Detailed Scorecard")
    if not selected_run_id:
        st.info("Run a batch evaluation first, or select a past run from the sidebar.")
    else:
        suppliers, warnings = load_run(selected_run_id)
        supplier_names = [s["supplier_name"] for s in suppliers]
        chosen = st.selectbox("Supplier", supplier_names)
        supplier = next(s for s in suppliers if s["supplier_name"] == chosen)

        st.metric("Absolute Score", round(supplier["absolute_score"], 2))
        st.metric("PPI", round(supplier["ppi"], 2))
        st.metric("Final Rank", supplier["final_rank"])

        crit_df = pd.DataFrame(
            [
                {
                    "Criterion": c["criterion_name"],
                    "Weight (%)": c["weight"],
                    "Score": f"{c['raw_score']}/{c['max_score']}",
                    "Weighted Contribution": round(c["weighted_contribution"], 2),
                    "Benchmark": c["benchmark_score"],
                    "Gap": c["gap"],
                    "Relative %": c["relative_pct"],
                }
                for c in supplier["criteria"]
            ]
        )
        st.dataframe(crit_df, use_container_width=True, hide_index=True)

        st.subheader("Evidence & Justification")
        for c in supplier["criteria"]:
            with st.expander(f"{c['criterion_name']} — score {c['raw_score']}/{c['max_score']}"):
                st.write(f"**Justification:** {c.get('justification', '')}")
                st.write(f"**Evidence:** {c.get('evidence', '')}")
                if c.get("was_normalized"):
                    st.warning(f"Normalized by the Validation Tool: {c.get('normalization_note')}")

# --------------------------------------------------------------------------------------
# Screen: Run Details
# --------------------------------------------------------------------------------------
with tab_run:
    st.header("Run Details")
    if not selected_run_id:
        st.info("Run a batch evaluation first, or select a past run from the sidebar.")
    else:
        suppliers, warnings = load_run(selected_run_id)
        st.write(f"**RFP_RUN_ID:** `{selected_run_id}`")

        st.subheader("Tie-break rule applied")
        st.write(tie_break_explanation())

        st.subheader("Validation warnings")
        if warnings:
            for w in warnings:
                st.warning(f"[{w['supplier_name']}] {w['warning_text']}")
        else:
            st.success("No validation warnings for this run.")

        st.subheader("Download complete result")
        export = {"rfp_run_id": selected_run_id, "suppliers": suppliers, "warnings": warnings}
        st.download_button(
            "Download JSON",
            data=json.dumps(export, indent=2),
            file_name=f"rfp_run_{selected_run_id}.json",
            mime="application/json",
        )
