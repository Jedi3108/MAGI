"""Deterministic mock backend for offline MAGI tests."""

from __future__ import annotations

import hashlib
import json
import random

def _stance_summary_for_vote(vote: str) -> str:
    vote = str(vote).strip().upper()

    if vote == "SUPPORT":
        return "I SUPPORT the target action."
    if vote == "OPPOSE":
        return "I OPPOSE the target action."
    if vote == "ABSTAIN":
        return "I ABSTAIN because evidence is insufficient."
    if vote == "INVALID_QUESTION":
        return "I REJECT THE QUESTION because the proposition framing is invalid."

    return "I ABSTAIN because the vote is unclear."


from magi.council.members import VALID_MEMBER_NAMES


def _vote_reason_alignment_for_vote(vote: str) -> str:
    vote = str(vote).strip().upper()

    if vote == "SUPPORT":
        return "I SUPPORT THE TARGET ACTION BECAUSE the mock council member accepts the proposed action."
    if vote == "OPPOSE":
        return "I OPPOSE THE TARGET ACTION BECAUSE the mock council member rejects the proposed action."
    if vote == "ABSTAIN":
        return "I ABSTAIN BECAUSE the mock council member lacks enough information."
    if vote == "INVALID_QUESTION":
        return "I REJECT THE QUESTION BECAUSE the mock council member finds the proposition malformed."

    return "I ABSTAIN BECAUSE the mock vote is unclear."


def _action_causality_for_vote(vote: str) -> str:
    vote = str(vote).strip().upper()

    if vote == "SUPPORT":
        return "IF THE TARGET ACTION IS TAKEN, THEN IT HELPS BECAUSE the mock action has expected benefits."
    if vote == "OPPOSE":
        return "IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE the mock action has expected risks."
    if vote == "ABSTAIN":
        return "IF THE TARGET ACTION IS TAKEN, THEN THE EFFECT IS UNCLEAR BECAUSE the mock evidence is incomplete."
    if vote == "INVALID_QUESTION":
        return "THE TARGET ACTION IS NOT WELL-DEFINED BECAUSE the mock proposition is malformed."

    return "IF THE TARGET ACTION IS TAKEN, THEN THE EFFECT IS UNCLEAR BECAUSE the mock vote is unclear."


def _counterfactual_comparison_for_vote(vote: str) -> str:
    vote = str(vote).strip().upper()

    if vote == "SUPPORT":
        return "TAKING THE TARGET ACTION IS BETTER THAN NOT TAKING IT BECAUSE the mock benefits outweigh the mock risks."
    if vote == "OPPOSE":
        return "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE the mock risks outweigh the mock benefits."
    if vote == "ABSTAIN":
        return "I CANNOT COMPARE TAKING VS NOT TAKING THE TARGET ACTION BECAUSE the mock evidence is incomplete."
    if vote == "INVALID_QUESTION":
        return "I CANNOT COMPARE OPTIONS BECAUSE THE QUESTION IS INVALID."

    return "I CANNOT COMPARE TAKING VS NOT TAKING THE TARGET ACTION BECAUSE the mock vote is unclear."


def mock_verdict(member_name: str, prompt: str) -> str:
    """Return a deterministic fake verdict as JSON."""
    seed = int(hashlib.sha256((member_name + prompt).encode("utf-8")).hexdigest(), 16)
    rng = random.Random(seed)

    vote = rng.choice(["SUPPORT", "OPPOSE"])
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
            "stance_summary": _stance_summary_for_vote(vote),
            "vote_reason_alignment": _vote_reason_alignment_for_vote(vote),
            "action_causality": _action_causality_for_vote(vote),
            "counterfactual_comparison": _counterfactual_comparison_for_vote(vote),
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
        if current_vote == "SUPPORT":
            vote_after = "OPPOSE"
        elif current_vote == "OPPOSE":
            vote_after = "SUPPORT"
        else:
            vote_after = current_vote

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


def mock_chair_dossier(decision: str, vote_split: str, prompt: str) -> str:
    """Return a deterministic fake Chair dossier as JSON."""
    seed = int(hashlib.sha256((decision + vote_split + prompt).encode("utf-8")).hexdigest(), 16)
    rng = random.Random(seed)

    return json.dumps(
        {
            "decision": decision,
            "vote_split": vote_split,
            "majority_reasoning": (
                "[MOCK] The majority position follows from the reflected votes "
                "and the dominant concerns raised during deliberation."
            ),
            "minority_reasoning": (
                "[MOCK] The minority position preserves an unresolved objection "
                "that should not be discarded."
            ),
            "key_risks": (
                "[MOCK] The main risk is over-interpreting a structured protocol "
                "as actual wisdom before using stronger models."
            ),
            "outstanding_uncertainties": (
                "[MOCK] The council still lacks external evidence and long-term memory."
            ),
            "required_conditions": (
                "[MOCK] Treat this as a provisional decision unless future evidence contradicts it."
            ),
            "recommended_next_action": rng.choice(
                [
                    "[MOCK] Proceed cautiously and record the decision trace.",
                    "[MOCK] Request more evidence before execution.",
                    "[MOCK] Accept the ruling but preserve the minority report.",
                ]
            ),
        }
    )
