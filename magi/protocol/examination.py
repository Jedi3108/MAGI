"""Cross-examination structures for the MAGI deliberation protocol."""

from __future__ import annotations

import json
from dataclasses import dataclass

from magi.council.members import VALID_MEMBER_NAMES
from magi.council.verdict import Verdict


VALID_SATISFACTION = {
    "SATISFIED",
    "PARTIALLY SATISFIED",
    "NOT SATISFIED",
}


@dataclass(frozen=True)
class RoutedQuestion:
    """A question asked by one council member to another."""

    asker_name: str
    target_name: str
    question: str


@dataclass
class CrossExaminationAnswer:
    """An answer given by a council member during cross-examination."""

    asker_name: str
    target_name: str
    question: str
    answer: str
    model: str
    raw: str = ""


@dataclass
class SatisfactionEvaluation:
    """The asker's evaluation of a cross-examination answer."""

    asker_name: str
    target_name: str
    question: str
    answer: str
    satisfaction: str
    reason: str
    confidence_delta: int
    model: str
    raw: str = ""


def collect_questions(verdicts: list[Verdict]) -> list[RoutedQuestion]:
    """Collect and validate questions from Round 1 verdicts."""
    questions: list[RoutedQuestion] = []

    for verdict in verdicts:
        target = verdict.question_for.strip().upper()
        question = verdict.question.strip()

        if target == "NO QUESTIONS":
            continue

        if target not in VALID_MEMBER_NAMES:
            continue

        if target == verdict.member_name:
            continue

        if not question or question.upper() == "NO QUESTIONS":
            continue

        questions.append(
            RoutedQuestion(
                asker_name=verdict.member_name,
                target_name=target,
                question=question,
            )
        )

    return questions


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


def _clean_satisfaction(value: object) -> str:
    text = str(value or "").strip().upper().replace("_", " ")

    if text in VALID_SATISFACTION:
        return text

    if "PARTIAL" in text:
        return "PARTIALLY SATISFIED"

    if "NOT" in text or "UNSATISFIED" in text:
        return "NOT SATISFIED"

    if "SATISFIED" in text:
        return "SATISFIED"

    return "PARTIALLY SATISFIED"


def _clean_confidence_delta(value: object) -> int:
    try:
        return max(-100, min(100, int(value)))
    except (TypeError, ValueError):
        return 0


def parse_cross_examination_answer(
    question: RoutedQuestion,
    raw: str,
    model: str,
) -> CrossExaminationAnswer:
    """Parse a target member's answer."""
    obj = _extract_json(raw)
    answer = str(obj.get("answer") or raw[:500]).strip()

    return CrossExaminationAnswer(
        asker_name=question.asker_name,
        target_name=question.target_name,
        question=question.question,
        answer=answer,
        model=model,
        raw=raw,
    )


def parse_satisfaction_evaluation(
    answer: CrossExaminationAnswer,
    raw: str,
    model: str,
) -> SatisfactionEvaluation:
    """Parse the asker's evaluation of an answer."""
    obj = _extract_json(raw)

    return SatisfactionEvaluation(
        asker_name=answer.asker_name,
        target_name=answer.target_name,
        question=answer.question,
        answer=answer.answer,
        satisfaction=_clean_satisfaction(obj.get("satisfaction")),
        reason=str(obj.get("reason") or raw[:500]).strip(),
        confidence_delta=_clean_confidence_delta(obj.get("confidence_delta")),
        model=model,
        raw=raw,
    )
