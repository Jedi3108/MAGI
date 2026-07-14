"""Tests for vote-matched stance summaries."""

import json
import unittest

from magi.council.members import MELCHIOR
from magi.council.verdict import parse_verdict
from magi.protocol.engine import JUDGE_INSTRUCTION


def raw(vote, stance):
    return json.dumps(
        {
            "target_action": "test action",
            "core_reason": "reason",
            "main_risk": "risk",
            "question_for": "NO QUESTIONS",
            "question": "NO QUESTIONS",
            "can_change_mind_if": "evidence",
            "stance_summary": stance,
            "vote_reason_alignment": {
                "SUPPORT": "I SUPPORT THE TARGET ACTION BECAUSE the reason supports the action.",
                "OPPOSE": "I OPPOSE THE TARGET ACTION BECAUSE the reason opposes the action.",
                "ABSTAIN": "I ABSTAIN BECAUSE evidence is insufficient.",
                "INVALID_QUESTION": "I REJECT THE QUESTION BECAUSE the framing is invalid.",
            }.get(vote, "I ABSTAIN BECAUSE the vote token is invalid."),
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


class TestStanceConsistency(unittest.TestCase):
    def test_support_requires_support_prefix(self):
        parsed = parse_verdict(MELCHIOR, raw("SUPPORT", "I SUPPORT the action."), "test-model")
        self.assertEqual(parsed.stance_summary, "I SUPPORT the action.")

    def test_oppose_requires_oppose_prefix(self):
        parsed = parse_verdict(MELCHIOR, raw("OPPOSE", "I OPPOSE the action."), "test-model")
        self.assertEqual(parsed.stance_summary, "I OPPOSE the action.")

    def test_abstain_requires_abstain_prefix(self):
        parsed = parse_verdict(MELCHIOR, raw("ABSTAIN", "I ABSTAIN because evidence is insufficient."), "test-model")
        self.assertEqual(parsed.vote, "ABSTAIN")

    def test_invalid_question_requires_reject_prefix(self):
        parsed = parse_verdict(MELCHIOR, raw("INVALID_QUESTION", "I REJECT THE QUESTION because it is a false binary."), "test-model")
        self.assertEqual(parsed.vote, "INVALID_QUESTION")

    def test_bare_oppose_stance_is_canonicalized(self):
        parsed = parse_verdict(MELCHIOR, raw("OPPOSE", "OPPOSE"), "test-model")
        self.assertEqual(parsed.stance_summary, "I OPPOSE the target action.")

    def test_bare_support_stance_is_canonicalized(self):
        parsed = parse_verdict(MELCHIOR, raw("SUPPORT", "SUPPORT"), "test-model")
        self.assertEqual(parsed.stance_summary, "I SUPPORT the target action.")

    def test_oppose_cannot_claim_support(self):
        with self.assertRaises(ValueError):
            parse_verdict(MELCHIOR, raw("OPPOSE", "I SUPPORT saving humans."), "test-model")

    def test_support_cannot_claim_opposition(self):
        with self.assertRaises(ValueError):
            parse_verdict(MELCHIOR, raw("SUPPORT", "I OPPOSE saving humans."), "test-model")

    def test_prompt_documents_required_prefixes(self):
        self.assertIn("If vote is SUPPORT, stance_summary must start with: I SUPPORT", JUDGE_INSTRUCTION)
        self.assertIn("If vote is OPPOSE, stance_summary must start with: I OPPOSE", JUDGE_INSTRUCTION)
        self.assertIn("If vote is ABSTAIN, stance_summary must start with: I ABSTAIN", JUDGE_INSTRUCTION)
        self.assertIn("If vote is INVALID_QUESTION, stance_summary must start with: I REJECT THE QUESTION", JUDGE_INSTRUCTION)


if __name__ == "__main__":
    unittest.main()
