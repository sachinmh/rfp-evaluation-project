"""Evaluation Agent: builds the grounded prompt and asks the LLM to score one supplier."""
from __future__ import annotations

from typing import Any

from core.llm_client import LLMClient

SYSTEM_PROMPT = """You are a procurement evaluation assistant. You score ONE supplier's RFP \
response against a fixed list of evaluation criteria.

Rules you must follow exactly:
1. Use ONLY evidence that is explicitly present in the supplier document text provided below. \
Do not invent, assume, or use outside knowledge about the supplier.
2. Return exactly one result for EVERY criterion listed, even if the document does not address \
it (in that case, give a low score and say so in the justification).
3. Each "score" must be a number between 0 and that criterion's "max_score", inclusive.
4. Output JSON only. No markdown fences, no commentary, no text before or after the JSON object.
5. You judge proposal content only. You must NOT compute weighted totals, rankings, or compare \
suppliers to each other — that is done deterministically outside this step.
"""

USER_PROMPT_TEMPLATE = """Supplier name: {supplier_name}

Evaluation criteria (score each one on a 0-{max_score_hint} scale unless stated otherwise):
{criteria_block}

Supplier document text:
\"\"\"
{document_text}
\"\"\"

Return JSON matching exactly this shape:
{{
  "supplier_name": "{supplier_name}",
  "criteria": [
    {{
      "criterion_id": <int>,
      "score": <number>,
      "max_score": <number>,
      "justification": "<short reason grounded in the document>",
      "evidence": "<short quote or paraphrase from the document>"
    }}
  ],
  "risks": ["<risk 1>", "..."],
  "overall_summary": "<2-3 sentence neutral summary>"
}}
"""


def build_prompt(criteria: list[dict[str, Any]], supplier_name: str, document_text: str) -> tuple[str, str]:
    criteria_block = "\n".join(
        f"- id={c['criterion_id']} | {c['name']} (weight {c['weight']}%, max_score {c['max_score']}): "
        f"{c.get('description', '')}"
        for c in criteria
    )
    max_score_hint = criteria[0]["max_score"] if criteria else 10
    user_prompt = USER_PROMPT_TEMPLATE.format(
        supplier_name=supplier_name,
        max_score_hint=max_score_hint,
        criteria_block=criteria_block,
        document_text=document_text[:15000],  # guard against extreme prompt sizes
    )
    return SYSTEM_PROMPT, user_prompt


def evaluate_supplier(
    llm_client: LLMClient,
    criteria: list[dict[str, Any]],
    supplier_name: str,
    document_text: str,
) -> str:
    """Returns the raw text response from the LLM (expected to be JSON)."""
    system_prompt, user_prompt = build_prompt(criteria, supplier_name, document_text)
    return llm_client.generate_json(system_prompt, user_prompt)
