"""Structured records for the non-voting MAGI Chair."""

from __future__ import annotations

from magi.protocol.reflection import Reflection


def _single_line(text: str) -> str:
    """Collapse text into a single safe line."""
    return " ".join(str(text).split())


def _names_for(reflections: list[Reflection], vote: str) -> str:
    names = [reflection.member_name for reflection in reflections if reflection.vote_after == vote]
    return ", ".join(names) if names else "None"


def build_structured_chair_record(reflections: list[Reflection]) -> str:
    """Build an authoritative final-vote record for the Chair.

    This record is intentionally compact and explicit so the Chair does not
    need to infer final positions from a long prose transcript.
    """
    support = sum(1 for reflection in reflections if reflection.vote_after == "SUPPORT")
    oppose = sum(1 for reflection in reflections if reflection.vote_after == "OPPOSE")
    abstain = sum(1 for reflection in reflections if reflection.vote_after == "ABSTAIN")
    invalid_question = sum(1 for reflection in reflections if reflection.vote_after == "INVALID_QUESTION")

    lines = [
        "AUTHORITATIVE FINAL REFLECTED VOTE RECORD",
        f"final_support_count={support}",
        f"final_oppose_count={oppose}",
        f"final_abstain_count={abstain}",
        f"final_invalid_question_count={invalid_question}",
        "",
        "FINAL POSITION GROUPS",
        f"SUPPORT: {_names_for(reflections, 'SUPPORT')}",
        f"OPPOSE: {_names_for(reflections, 'OPPOSE')}",
        f"ABSTAIN: {_names_for(reflections, 'ABSTAIN')}",
        f"INVALID_QUESTION: {_names_for(reflections, 'INVALID_QUESTION')}",
        "",
        "MEMBER FINAL POSITIONS",
    ]

    for reflection in reflections:
        lines.append(
            "- "
            f"{reflection.member_name} ({reflection.member_title}): "
            f"final_vote={reflection.vote_after}; "
            f"final_confidence={reflection.confidence_after}; "
            f"round1_vote={reflection.vote_before}; "
            f"round1_confidence={reflection.confidence_before}; "
            f"learned={_single_line(reflection.learned)}; "
            f"final_reason={_single_line(reflection.reason)}"
        )

    return "\n".join(lines)
