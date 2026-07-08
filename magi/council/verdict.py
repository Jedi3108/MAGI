"""Council verdict structures and parsing."""

from __future__ import annotations

from dataclasses import dataclass

from magi.council.members import CouncilMember, VALID_MEMBER_NAMES
from magi.utils.json_tools import extract_json_object, int_field, text_field


@dataclass
class Verdict:
    """Structured Round 1 output from a council member."""

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


def _clean_vote(value: object) -> str:
    vote = str(value or "").strip().upper()

    if vote in {"AFFIRMATIVE", "NEGATIVE"}:
        return vote

    return "NEGATIVE"


def _clean_question_for(value: object, raw: str) -> str:
    question_for = str(value or "").strip().upper()

    if question_for in VALID_MEMBER_NAMES:
        return question_for

    if question_for == "NO QUESTIONS":
        return "NO QUESTIONS"

    recovered = text_field({}, raw, "question_for", "NO QUESTIONS").strip().upper()

    if recovered in VALID_MEMBER_NAMES:
        return recovered

    return "NO QUESTIONS"


def parse_verdict(member: CouncilMember, raw: str, model: str) -> Verdict:
    """Parse a model response into a Verdict."""
    obj = extract_json_object(raw)

    vote = _clean_vote(text_field(obj, raw, "vote", "NEGATIVE"))
    question_for = _clean_question_for(obj.get("question_for"), raw)
    question = text_field(obj, raw, "question", "NO QUESTIONS")

    if question_for == member.name:
        question_for = "NO QUESTIONS"
        question = "NO QUESTIONS"

    return Verdict(
        member_name=member.name,
        member_title=member.title,
        vote=vote,
        confidence=int_field(obj, raw, "confidence", 50, 0, 100),
        core_reason=text_field(
            obj,
            raw,
            "core_reason",
            "No valid core reason provided.",
        ),
        main_risk=text_field(
            obj,
            raw,
            "main_risk",
            "No valid risk provided.",
        ),
        question_for=question_for,
        question=question,
        can_change_mind_if=text_field(
            obj,
            raw,
            "can_change_mind_if",
            "No valid change condition provided.",
        ),
        model=model,
        raw=raw,
    )
