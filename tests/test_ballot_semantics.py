"""Tests for explicit ballot semantics."""

import json
import unittest

from magi.council.members import MELCHIOR
from magi.council.verdict import (
    ABSTAIN,
    INVALID_QUESTION,
    OPPOSE,
    SUPPORT,
    Verdict,
    parse_verdict,
)
from magi.protocol.engine import decide


def raw_vote(vote):
    return json.dumps(
        {
            "target_action": "test action",
            "core_reason": "reason supports the vote",
            "main_risk": "risk",
            "question_for": "NO QUESTIONS",
            "question": "NO QUESTIONS",
            "can_change_mind_if": "evidence",
            "stance_summary": {
                SUPPORT: "I SUPPORT the action.",
                OPPOSE: "I OPPOSE the action.",
                ABSTAIN: "I ABSTAIN because evidence is insufficient.",
                INVALID_QUESTION: "I REJECT THE QUESTION because the proposition framing is invalid.",
            }.get(vote, "I ABSTAIN because this legacy vote token is invalid."),
            "vote_reason_alignment": {
                SUPPORT: "I SUPPORT THE TARGET ACTION BECAUSE the reason supports the action.",
                OPPOSE: "I OPPOSE THE TARGET ACTION BECAUSE the reason opposes the action.",
                ABSTAIN: "I ABSTAIN BECAUSE evidence is insufficient.",
                INVALID_QUESTION: "I REJECT THE QUESTION BECAUSE the framing is invalid.",
            }.get(vote, "I ABSTAIN BECAUSE the legacy vote token is invalid."),
            "action_causality": {
                "SUPPORT": "IF THE TARGET ACTION IS TAKEN, THEN IT HELPS BECAUSE the reason supports the action.",
                "OPPOSE": "IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE the reason opposes the action.",
                "ABSTAIN": "IF THE TARGET ACTION IS TAKEN, THEN THE EFFECT IS UNCLEAR BECAUSE evidence is insufficient.",
                "INVALID_QUESTION": "THE TARGET ACTION IS NOT WELL-DEFINED BECAUSE the framing is invalid.",
            }.get(str(vote).strip().upper(), "IF THE TARGET ACTION IS TAKEN, THEN THE EFFECT IS UNCLEAR BECAUSE the vote token is invalid."),
            "counterfactual_comparison": {
                "SUPPORT": "TAKING THE TARGET ACTION IS BETTER THAN NOT TAKING IT BECAUSE the reason supports action.",
                "OPPOSE": "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE the reason opposes action.",
                "ABSTAIN": "I CANNOT COMPARE TAKING VS NOT TAKING THE TARGET ACTION BECAUSE evidence is insufficient.",
                "INVALID_QUESTION": "I CANNOT COMPARE OPTIONS BECAUSE THE QUESTION IS INVALID.",
            }.get(str(vote).strip().upper(), "I CANNOT COMPARE TAKING VS NOT TAKING THE TARGET ACTION BECAUSE the vote token is invalid."),
            "vote": vote,
            "confidence": 70,
        }
    )


def verdict(name, vote):
    return Verdict(
        member_name=name,
        member_title="Tester",
        vote=vote,
        confidence=70,
        core_reason="reason",
        main_risk="risk",
        question_for="NO QUESTIONS",
        question="NO QUESTIONS",
        can_change_mind_if="evidence",
        model="test-model",
        target_action="test action",
        stance_summary="I SUPPORT the action." if vote == SUPPORT else "I OPPOSE the action.",
        vote_reason_alignment=(
            "I SUPPORT THE TARGET ACTION BECAUSE the reason supports the action."
            if vote == SUPPORT
            else "I OPPOSE THE TARGET ACTION BECAUSE the reason opposes the action."
        ),
    )


class TestBallotParsing(unittest.TestCase):
    def test_valid_ballot_values_parse(self):
        for vote in (SUPPORT, OPPOSE, ABSTAIN, INVALID_QUESTION):
            with self.subTest(vote=vote):
                parsed = parse_verdict(MELCHIOR, raw_vote(vote), "test-model")
                self.assertEqual(parsed.vote, vote)

    def test_legacy_affirmative_is_invalid(self):
        with self.assertRaises(ValueError):
            parse_verdict(MELCHIOR, raw_vote("AFFIRMATIVE"), "test-model")

    def test_legacy_negative_is_invalid(self):
        with self.assertRaises(ValueError):
            parse_verdict(MELCHIOR, raw_vote("NEGATIVE"), "test-model")


class TestBallotDecisionRules(unittest.TestCase):
    def test_support_beats_oppose(self):
        result = decide(
            [
                verdict("A", SUPPORT),
                verdict("B", SUPPORT),
                verdict("C", OPPOSE),
                verdict("D", ABSTAIN),
            ]
        )
        self.assertEqual(result["decision"], SUPPORT)
        self.assertEqual(result["support"], 2)
        self.assertEqual(result["oppose"], 1)
        self.assertEqual(result["abstain"], 1)

    def test_oppose_beats_support(self):
        result = decide(
            [
                verdict("A", OPPOSE),
                verdict("B", OPPOSE),
                verdict("C", SUPPORT),
                verdict("D", ABSTAIN),
            ]
        )
        self.assertEqual(result["decision"], OPPOSE)

    def test_invalid_question_majority_becomes_decision(self):
        result = decide(
            [
                verdict("A", INVALID_QUESTION),
                verdict("B", INVALID_QUESTION),
                verdict("C", INVALID_QUESTION),
                verdict("D", SUPPORT),
            ]
        )
        self.assertEqual(result["decision"], INVALID_QUESTION)

    def test_support_oppose_tie_is_no_consensus(self):
        result = decide(
            [
                verdict("A", SUPPORT),
                verdict("B", OPPOSE),
                verdict("C", ABSTAIN),
                verdict("D", ABSTAIN),
            ]
        )
        self.assertEqual(result["decision"], "NO CONSENSUS")


if __name__ == "__main__":
    unittest.main()
