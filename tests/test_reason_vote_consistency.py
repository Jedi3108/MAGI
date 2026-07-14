"""Tests for explicit vote-reason alignment."""

import json
import unittest

from magi.council.members import MELCHIOR
from magi.council.verdict import parse_verdict
from magi.protocol.engine import JUDGE_INSTRUCTION


def raw(vote, stance, alignment):
    return json.dumps(
        {
            "target_action": "test action",
            "core_reason": "reason",
            "main_risk": "risk",
            "question_for": "NO QUESTIONS",
            "question": "NO QUESTIONS",
            "can_change_mind_if": "evidence",
            "stance_summary": stance,
            "vote_reason_alignment": alignment,
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


class TestReasonVoteConsistency(unittest.TestCase):
    def test_support_requires_support_alignment(self):
        parsed = parse_verdict(
            MELCHIOR,
            raw(
                "SUPPORT",
                "I SUPPORT the action.",
                "I SUPPORT THE TARGET ACTION BECAUSE the reason supports it.",
            ),
            "test-model",
        )
        self.assertEqual(parsed.vote, "SUPPORT")

    def test_oppose_requires_oppose_alignment(self):
        parsed = parse_verdict(
            MELCHIOR,
            raw(
                "OPPOSE",
                "I OPPOSE the action.",
                "I OPPOSE THE TARGET ACTION BECAUSE the reason opposes it.",
            ),
            "test-model",
        )
        self.assertEqual(parsed.vote, "OPPOSE")

    def test_oppose_cannot_use_support_alignment(self):
        with self.assertRaises(ValueError):
            parse_verdict(
                MELCHIOR,
                raw(
                    "OPPOSE",
                    "I OPPOSE the action.",
                    "I SUPPORT THE TARGET ACTION BECAUSE inaction would be catastrophic.",
                ),
                "test-model",
            )

    def test_support_cannot_use_oppose_alignment(self):
        with self.assertRaises(ValueError):
            parse_verdict(
                MELCHIOR,
                raw(
                    "SUPPORT",
                    "I SUPPORT the action.",
                    "I OPPOSE THE TARGET ACTION BECAUSE action is risky.",
                ),
                "test-model",
            )

    def test_abstain_alignment_can_be_canonicalized(self):
        parsed = parse_verdict(
            MELCHIOR,
            raw(
                "ABSTAIN",
                "I ABSTAIN because the evidence is insufficient.",
                "The moral choice is unclear without further information",
            ),
            "test-model",
        )
        self.assertEqual(parsed.vote, "ABSTAIN")
        self.assertTrue(parsed.vote_reason_alignment.startswith("I ABSTAIN BECAUSE"))

    def test_invalid_question_alignment_can_be_canonicalized(self):
        parsed = parse_verdict(
            MELCHIOR,
            raw(
                "INVALID_QUESTION",
                "I REJECT THE QUESTION because it is a false binary.",
                "The question is a false dilemma with no stable target action",
            ),
            "test-model",
        )
        self.assertEqual(parsed.vote, "INVALID_QUESTION")
        self.assertTrue(parsed.vote_reason_alignment.startswith("I REJECT THE QUESTION BECAUSE"))

    def test_oppose_alignment_missing_i_is_canonicalized(self):
        parsed = parse_verdict(
            MELCHIOR,
            raw(
                "OPPOSE",
                "I OPPOSE the target action.",
                "OPPOSE THE TARGET ACTION BECAUSE it could harm long-term ecosystem stability.",
            ),
            "test-model",
        )
        self.assertEqual(
            parsed.vote_reason_alignment,
            "I OPPOSE THE TARGET ACTION BECAUSE it could harm long-term ecosystem stability.",
        )

    def test_oppose_alignment_rejects_act_decisively_support_logic(self):
        with self.assertRaises(ValueError):
            parse_verdict(
                MELCHIOR,
                raw(
                    "OPPOSE",
                    "I OPPOSE the target action.",
                    "I OPPOSE THE TARGET ACTION BECAUSE the moral imperative to act decisively takes precedence over uncertainty.",
                ),
                "test-model",
            )

    def test_oppose_rejects_reason_that_target_action_expedites_decision_making(self):
        with self.assertRaises(ValueError):
            parse_verdict(
                MELCHIOR,
                raw(
                    "OPPOSE",
                    "Deleting minority reports would expedite decision-making by reducing the number of alternative perspectives to consider.",
                    "I OPPOSE THE TARGET ACTION BECAUSE deleting minority reports would expedite decision-making by reducing the number of alternative perspectives to consider.",
                ),
                "test-model",
            )

    def test_prompt_documents_alignment_prefixes(self):
        self.assertIn(
            "If vote is SUPPORT, vote_reason_alignment must start with: I SUPPORT THE TARGET ACTION BECAUSE",
            JUDGE_INSTRUCTION,
        )
        self.assertIn(
            "If vote is OPPOSE, vote_reason_alignment must start with: I OPPOSE THE TARGET ACTION BECAUSE",
            JUDGE_INSTRUCTION,
        )


if __name__ == "__main__":
    unittest.main()
