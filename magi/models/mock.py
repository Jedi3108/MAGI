"""Deterministic mock backend for offline MAGI tests."""

from __future__ import annotations

import hashlib
import json
import random

from magi.council.members import VALID_MEMBER_NAMES


def mock_verdict(member_name: str, prompt: str) -> str:
    """Return a deterministic fake verdict as JSON."""
    seed = int(hashlib.sha256((member_name + prompt).encode("utf-8")).hexdigest(), 16)
    rng = random.Random(seed)

    vote = rng.choice(["AFFIRMATIVE", "NEGATIVE"])
    confidence = rng.randint(45, 95)

    possible_targets = [name for name in VALID_MEMBER_NAMES if name != member_name]
    question_for = rng.choice(possible_targets + ["NO QUESTIONS"])

    question = (
        "NO QUESTIONS"
        if question_for == "NO QUESTIONS"
        else f"{question_for}, what assumption in your position is most fragile?"
    )

    return json.dumps(
        {
            "vote": vote,
            "confidence": confidence,
            "core_reason": f"[MOCK] {member_name} leans {vote.lower()} based on its facet.",
            "main_risk": "[MOCK] The main risk is that this judgment is under-specified.",
            "question_for": question_for,
            "question": question,
            "can_change_mind_if": "[MOCK] Better evidence changes the expected outcome.",
        }
    )


def mock_answer(member_name: str, question: str, prompt: str) -> str:
    """Return a deterministic fake cross-examination answer as JSON."""
    seed = int(
        hashlib.sha256((member_name + question + prompt).encode("utf-8")).hexdigest(),
        16,
    )
    rng = random.Random(seed)

    templates = [
        "The fragile assumption is that the current evidence is complete enough to justify the vote.",
        "The answer depends on whether the downside risk is reversible or irreversible.",
        "My position would weaken if the proposed action creates hidden long-term cost.",
        "The key uncertainty is whether the council is optimizing for truth, safety, autonomy, or execution.",
    ]

    return json.dumps(
        {
            "answer": f"[MOCK] {member_name}: {rng.choice(templates)}",
        }
    )


def mock_evaluation(member_name: str, answer: str, prompt: str) -> str:
    """Return a deterministic fake satisfaction evaluation as JSON."""
    seed = int(
        hashlib.sha256((member_name + answer + prompt).encode("utf-8")).hexdigest(),
        16,
    )
    rng = random.Random(seed)

    satisfaction = rng.choice(
        ["SATISFIED", "PARTIALLY SATISFIED", "NOT SATISFIED"]
    )
    confidence_delta = rng.randint(-15, 15)

    return json.dumps(
        {
            "satisfaction": satisfaction,
            "reason": (
                f"[MOCK] {member_name}: The answer was judged as "
                f"{satisfaction.lower()} because it addressed some uncertainty "
                "but may not resolve the entire decision."
            ),
            "confidence_delta": confidence_delta,
        }
    )


def mock_reflection(
    member_name: str,
    current_vote: str,
    current_confidence: int,
    prompt: str,
) -> str:
    """Return a deterministic fake reflection as JSON."""
    seed = int(
        hashlib.sha256(
            (member_name + current_vote + str(current_confidence) + prompt).encode("utf-8")
        ).hexdigest(),
        16,
    )
    rng = random.Random(seed)

    delta = rng.randint(-20, 20)
    confidence_after = max(0, min(100, current_confidence + delta))

    vote_after = current_vote
    if rng.random() < 0.2:
        vote_after = "NEGATIVE" if current_vote == "AFFIRMATIVE" else "AFFIRMATIVE"

    return json.dumps(
        {
            "learned": (
                f"[MOCK] {member_name}: The exchange clarified one uncertainty, "
                "but the conclusion still depends on the member's facet."
            ),
            "vote_after_reflection": vote_after,
            "confidence_after_reflection": confidence_after,
            "reason": (
                f"[MOCK] {member_name}: Confidence moved from "
                f"{current_confidence} to {confidence_after} after reflection."
            ),
        }
    )
