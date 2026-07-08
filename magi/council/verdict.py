"""Structured verdicts returned by MAGI council members."""

from __future__ import annotations

import json
from dataclasses import dataclass

from magi.council.members import CouncilMember, VALID_MEMBER_NAMES


@dataclass
class Verdict:
    """A structured council statement."""

    member_name: str
    member_title: str
    vote: str
    confidence: int
    core_reason: str
    main_risk: str
    question_for: str
    question: str
    can_change_mind_if: str
    model: str
    raw: str = ""

    @property
    def approves(self) -> bool:
        return self.vote == "AFFIRMATIVE"


def _extract_json(raw: str) -> dict:
    """Best-effort JSON extraction from model output."""
    text = raw.strip()
    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return {}

    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}


def _clean_vote(value: object, raw: str) -> str:
    vote = str(value or "").strip().upper()
    if vote in {"AFFIRMATIVE", "NEGATIVE"}:
        return vote

    low = raw.lower()
    return "AFFIRMATIVE" if low.count("affirmative") >= low.count("negative") else "NEGATIVE"


def _clean_confidence(value: object) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return 60


def _clean_question_for(value: object, fallback: str) -> str:
    target = str(value or fallback).strip().upper()
    if target in VALID_MEMBER_NAMES or target == "NO QUESTIONS":
        return target
    return fallback


def parse_verdict(member: CouncilMember, raw: str, model: str) -> Verdict:
    """Parse a council member response into a Verdict."""
    obj = _extract_json(raw)

    vote = _clean_vote(obj.get("vote"), raw)
    confidence = _clean_confidence(obj.get("confidence"))
    question_for = _clean_question_for(obj.get("question_for"), fallback="NO QUESTIONS")

    return Verdict(
        member_name=member.name,
        member_title=member.title,
        vote=vote,
        confidence=confidence,
        core_reason=str(obj.get("core_reason") or obj.get("reasoning") or raw[:240]).strip(),
        main_risk=str(obj.get("main_risk") or "No explicit risk stated.").strip(),
        question_for=question_for,
        question=str(obj.get("question") or "NO QUESTIONS").strip(),
        can_change_mind_if=str(
            obj.get("can_change_mind_if") or "Stronger evidence or reasoning is provided."
        ).strip(),
        model=model,
        raw=raw,
    )
