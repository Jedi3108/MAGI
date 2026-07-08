"""Structured records for the non-voting MAGI Chair."""

from __future__ import annotations

from magi.protocol.reflection import Reflection


def _single_line(text: str) -> str:
    """Collapse text into a single safe line."""
    return " ".join(str(text).split())


def build_structured_chair_record(reflections: list[Reflection]) -> str:
    """Build an authoritative final-vote record for the Chair.

    This record is intentionally compact and explicit so the Chair does not
    need to infer final positions from a long prose transcript.
    """
    affirmative = sum(1 for reflection in reflections if reflection.vote_after == "AFFIRMATIVE")
    negative = sum(1 for reflection in reflections if reflection.vote_after == "NEGATIVE")

    lines = [
        "AUTHORITATIVE FINAL REFLECTED VOTE RECORD",
        f"final_affirmative_count={affirmative}",
        f"final_negative_count={negative}",
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
