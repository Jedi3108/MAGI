"""Reflection structures for the MAGI deliberation protocol."""

from __future__ import annotations

import json
from dataclasses import dataclass

from magi.council.members import CouncilMember
from magi.council.verdict import Verdict


@dataclass
class Reflection:
    """A council member's reflection after cross-examination and evaluation."""

    member_name: str
    member_title: str
    vote_before: str
    vote_after: str
    confidence_before: int
    confidence_after: int
    learned: str
    reason: str
    model: str
    raw: str = ""

    @property
    def approves(self) -> bool:
        return self.vote_after == "AFFIRMATIVE"


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


def _clean_vote(value: object, fallback: str) -> str:
    vote = str(value or fallback).strip().upper()
    if vote in {"AFFIRMATIVE", "NEGATIVE"}:
        return vote
    return fallback


def _clean_confidence(value: object, fallback: int) -> int:
    try:
        return max(0, min(100, int(value)))
    except (TypeError, ValueError):
        return fallback


def parse_reflection(
    member: CouncilMember,
    verdict: Verdict,
    raw: str,
    model: str,
) -> Reflection:
    """Parse a reflection response."""
    obj = _extract_json(raw)

    return Reflection(
        member_name=member.name,
        member_title=member.title,
        vote_before=verdict.vote,
        vote_after=_clean_vote(obj.get("vote_after_reflection"), verdict.vote),
        confidence_before=verdict.confidence,
        confidence_after=_clean_confidence(
            obj.get("confidence_after_reflection"),
            verdict.confidence,
        ),
        learned=str(obj.get("learned") or "No explicit learning stated.").strip(),
        reason=str(obj.get("reason") or raw[:500]).strip(),
        model=model,
        raw=raw,
    )
