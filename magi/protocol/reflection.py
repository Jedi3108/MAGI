"""Reflection structures for the MAGI deliberation protocol."""

from __future__ import annotations

from dataclasses import dataclass

from magi.council.members import CouncilMember
from magi.council.verdict import ABSTAIN, DECISIVE_VOTES, INVALID_QUESTION, OPPOSE, SUPPORT, VALID_VOTES, Verdict
from magi.utils.json_tools import extract_json_object, int_field, text_field


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
    def supports(self) -> bool:
        return self.vote_after == SUPPORT

    @property
    def opposes(self) -> bool:
        return self.vote_after == OPPOSE

    @property
    def abstains(self) -> bool:
        return self.vote_after == ABSTAIN

    @property
    def invalid_question(self) -> bool:
        return self.vote_after == INVALID_QUESTION

    @property
    def decisive(self) -> bool:
        return self.vote_after in DECISIVE_VOTES

    @property
    def approves(self) -> bool:
        """Backward-compatible alias for old SUPPORT/OPPOSE code paths."""
        return self.supports


def _clean_vote(value: object) -> str:
    vote = str(value or "").strip().upper()

    if vote in VALID_VOTES:
        return vote

    raise ValueError(f"Invalid reflection vote token: {value!r}")


def parse_reflection(
    member: CouncilMember,
    verdict: Verdict,
    raw: str,
    model: str,
) -> Reflection:
    """Parse a reflection response."""
    obj = extract_json_object(raw)

    vote_raw = text_field(obj, raw, "vote_after_reflection", None)

    return Reflection(
        member_name=member.name,
        member_title=member.title,
        vote_before=verdict.vote,
        vote_after=_clean_vote(vote_raw),
        confidence_before=verdict.confidence,
        confidence_after=int_field(
            obj,
            raw,
            "confidence_after_reflection",
            verdict.confidence,
            0,
            100,
        ),
        learned=text_field(
            obj,
            raw,
            "learned",
            "No valid learning statement provided.",
        ),
        reason=text_field(
            obj,
            raw,
            "reason",
            "No valid reflection reason provided.",
        ),
        model=model,
        raw=raw,
    )
