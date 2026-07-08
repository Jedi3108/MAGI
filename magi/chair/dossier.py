"""Decision dossier produced by the non-voting MAGI Chair."""

from __future__ import annotations

from dataclasses import dataclass

from magi.utils.json_tools import extract_json_object, text_field


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
    obj = extract_json_object(raw)

    return DecisionDossier(
        decision=_clean_decision(
            text_field(obj, raw, "decision", fallback_decision),
            fallback_decision,
        ),
        vote_split=text_field(obj, raw, "vote_split", fallback_split),
        majority_reasoning=text_field(
            obj,
            raw,
            "majority_reasoning",
            "No valid majority reasoning provided.",
        ),
        minority_reasoning=text_field(
            obj,
            raw,
            "minority_reasoning",
            "No valid minority reasoning provided.",
        ),
        key_risks=text_field(
            obj,
            raw,
            "key_risks",
            "No valid key risks provided.",
        ),
        outstanding_uncertainties=text_field(
            obj,
            raw,
            "outstanding_uncertainties",
            "No valid outstanding uncertainties provided.",
        ),
        required_conditions=text_field(
            obj,
            raw,
            "required_conditions",
            "No valid required conditions provided.",
        ),
        recommended_next_action=text_field(
            obj,
            raw,
            "recommended_next_action",
            "No valid next action provided.",
        ),
        model=model,
        raw=raw,
    )
