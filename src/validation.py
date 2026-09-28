"""
Validation Tool: parses the LLM's raw JSON text, checks it against a Pydantic schema,
and normalizes missing/malformed/out-of-range results before any scoring happens.

Every normalization decision is recorded as a warning so the run stays explainable.
"""
from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError, field_validator


class RawCriterionScore(BaseModel):
    criterion_id: int
    score: float
    max_score: float | None = None
    justification: str = ""
    evidence: str = ""

    @field_validator("score", "max_score", mode="before")
    @classmethod
    def _coerce_numeric(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            match = re.search(r"-?\d+(\.\d+)?", v)
            if match:
                return float(match.group())
            raise ValueError(f"Cannot parse numeric value from {v!r}")
        return v


class RawLLMResponse(BaseModel):
    supplier_name: str = ""
    criteria: list[RawCriterionScore] = []
    risks: list[str] = []
    overall_summary: str = ""


def _extract_json_block(text: str) -> str:
    """Strip markdown code fences etc. if the model wrapped the JSON despite instructions."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        return text[brace_start : brace_end + 1]
    return text


def normalize_llm_output(
    raw_text: str,
    active_criteria: list[dict[str, Any]],
    supplier_name: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Returns (normalized_criteria, warnings).

    normalized_criteria: one dict per active criterion, always present, always in-range.
    warnings: human-readable strings describing every correction that was made.
    """
    warnings: list[str] = []
    parsed: RawLLMResponse

    json_block = _extract_json_block(raw_text)
    try:
        data = json.loads(json_block)
        parsed = RawLLMResponse.model_validate(data)
    except (json.JSONDecodeError, ValidationError) as exc:
        warnings.append(
            f"LLM output for '{supplier_name}' was unparsable ({exc.__class__.__name__}); "
            "all criteria defaulted to 0."
        )
        parsed = RawLLMResponse(supplier_name=supplier_name)

    by_id = {c.criterion_id: c for c in parsed.criteria}

    normalized: list[dict[str, Any]] = []
    for crit in active_criteria:
        cid = crit["criterion_id"]
        configured_max = float(crit["max_score"])
        entry = by_id.get(cid)

        if entry is None:
            warnings.append(
                f"'{supplier_name}': criterion '{crit['name']}' (id={cid}) missing from LLM "
                "output; defaulted to score 0."
            )
            normalized.append(
                {
                    "criterion_id": cid,
                    "criterion_name": crit["name"],
                    "weight": crit["weight"],
                    "raw_score": 0.0,
                    "max_score": configured_max,
                    "justification": "No result returned by the model for this criterion.",
                    "evidence": "",
                    "was_normalized": True,
                    "normalization_note": "missing_criterion",
                }
            )
            continue

        score = entry.score
        was_normalized = False
        note = ""

        if score < 0:
            warnings.append(
                f"'{supplier_name}': criterion '{crit['name']}' had negative score {score}; clipped to 0."
            )
            score = 0.0
            was_normalized = True
            note = "clipped_negative"
        elif score > configured_max:
            warnings.append(
                f"'{supplier_name}': criterion '{crit['name']}' score {score} exceeded max "
                f"{configured_max}; clipped."
            )
            score = configured_max
            was_normalized = True
            note = "clipped_over_max"

        normalized.append(
            {
                "criterion_id": cid,
                "criterion_name": crit["name"],
                "weight": crit["weight"],
                "raw_score": score,
                "max_score": configured_max,
                "justification": entry.justification,
                "evidence": entry.evidence,
                "was_normalized": was_normalized,
                "normalization_note": note,
            }
        )

    extra_ids = set(by_id.keys()) - {c["criterion_id"] for c in active_criteria}
    for eid in extra_ids:
        warnings.append(
            f"'{supplier_name}': LLM returned an unexpected criterion_id={eid} not in the "
            "active criteria set; ignored."
        )

    return normalized, warnings
