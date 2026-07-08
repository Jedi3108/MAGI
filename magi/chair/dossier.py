"""Decision dossier produced by the non-voting MAGI Chair."""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class DecisionDossier:
    """Final non-voting Chair summary of a MAGI deliberation."""

    decision: str
    vote_split: str
    majority_reasoning: str
    minority_reasoning: str
    key_risks: str
    outstanding_uncertainties: str
    required_conditions: str
    recommended_next_action: str
    model: str
    raw: str = ""


def _extract_json(raw: str) -> dict:
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return {}

    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}


def _clean_decision(value: object, fallback: str) -> str:
    decision = str(value or fallback).strip().upper()
    if decision in {"AFFIRMATIVE", "NEGATIVE", "NO CONSENSUS"}:
        return decision
    return fallback


def parse_decision_dossier(
    raw: str,
    model: str,
    fallback_decision: str,
    fallback_split: str,
) -> DecisionDossier:
    """Parse the Chair output into a DecisionDossier."""
    obj = _extract_json(raw)

    return DecisionDossier(
        decision=_clean_decision(obj.get("decision"), fallback_decision),
        vote_split=str(obj.get("vote_split") or fallback_split).strip(),
        majority_reasoning=str(
            obj.get("majority_reasoning") or "No majority reasoning provided."
        ).strip(),
        minority_reasoning=str(
            obj.get("minority_reasoning") or "No minority reasoning provided."
        ).strip(),
        key_risks=str(obj.get("key_risks") or "No key risks provided.").strip(),
        outstanding_uncertainties=str(
            obj.get("outstanding_uncertainties") or "No outstanding uncertainties provided."
        ).strip(),
        required_conditions=str(
            obj.get("required_conditions") or "No required conditions provided."
        ).strip(),
        recommended_next_action=str(
            obj.get("recommended_next_action") or "No next action provided."
        ).strip(),
        model=model,
        raw=raw,
    )
