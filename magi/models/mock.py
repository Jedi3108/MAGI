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
