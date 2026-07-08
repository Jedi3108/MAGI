"""Cross-examination structures for the MAGI deliberation protocol."""

from __future__ import annotations

from dataclasses import dataclass

from magi.council.members import VALID_MEMBER_NAMES
from magi.council.verdict import Verdict
from magi.utils.json_tools import extract_json_object, int_field, text_field


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


def parse_cross_examination_answer(
    question: RoutedQuestion,
    raw: str,
    model: str,
) -> CrossExaminationAnswer:
    """Parse a target member's answer."""
    obj = extract_json_object(raw)

    return CrossExaminationAnswer(
        asker_name=question.asker_name,
        target_name=question.target_name,
        question=question.question,
        answer=text_field(obj, raw, "answer", "No valid answer provided."),
        model=model,
        raw=raw,
    )


def parse_satisfaction_evaluation(
    answer: CrossExaminationAnswer,
    raw: str,
    model: str,
) -> SatisfactionEvaluation:
    """Parse the asker's evaluation of an answer."""
    obj = extract_json_object(raw)

    satisfaction_raw = text_field(
        obj,
        raw,
        "satisfaction",
        "PARTIALLY SATISFIED",
    )

    return SatisfactionEvaluation(
        asker_name=answer.asker_name,
        target_name=answer.target_name,
        question=answer.question,
        answer=answer.answer,
        satisfaction=_clean_satisfaction(satisfaction_raw),
        reason=text_field(
            obj,
            raw,
            "reason",
            "No valid satisfaction reason provided.",
        ),
        confidence_delta=int_field(
            obj,
            raw,
            "confidence_delta",
            0,
            -100,
            100,
        ),
        model=model,
        raw=raw,
    )
