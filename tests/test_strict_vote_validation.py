"""Tests for strict vote validation.

MAGI must never manufacture a OPPOSE vote when the model output is missing,
empty, malformed, or ambiguous. A malformed vote is a protocol failure, not a
decision.
"""

import json
import unittest

from magi.council.members import MELCHIOR
from magi.council.verdict import parse_verdict
from magi.protocol.reflection import parse_reflection

def stance_for(vote: str) -> str:
    vote = str(vote).strip().upper()

    return {
        "SUPPORT": "I SUPPORT the action.",
        "OPPOSE": "I OPPOSE the action.",
        "ABSTAIN": "I ABSTAIN because evidence is insufficient.",
        "INVALID_QUESTION": "I REJECT THE QUESTION because the proposition framing is invalid.",
    }.get(vote, "I ABSTAIN because evidence is insufficient.")



def valid_verdict_raw(vote="SUPPORT"):
    return json.dumps(
        {
            "core_reason": "the reason supports the decision",
            "main_risk": "a concrete risk",
            "question_for": "NO QUESTIONS",
            "question": "NO QUESTIONS",
            "can_change_mind_if": "better evidence",
            "stance_summary": stance_for(vote),
            "vote": vote,
            "confidence": 70,
        }
    )


def valid_reflection_raw(vote="SUPPORT"):
    return json.dumps(
        {
            "learned": "I learned something relevant",
            "reason": "the reflected reason supports the final vote",
            "vote_after_reflection": vote,
            "confidence_after_reflection": 65,
        }
    )


class TestStrictVerdictVoteValidation(unittest.TestCase):
    def test_valid_support_vote_parses(self):
        verdict = parse_verdict(MELCHIOR, valid_verdict_raw("SUPPORT"), "test-model")
        self.assertEqual(verdict.vote, "SUPPORT")

    def test_valid_oppose_vote_parses(self):
        verdict = parse_verdict(MELCHIOR, valid_verdict_raw("OPPOSE"), "test-model")
        self.assertEqual(verdict.vote, "OPPOSE")

    def test_lowercase_vote_is_normalized(self):
        verdict = parse_verdict(MELCHIOR, valid_verdict_raw("support"), "test-model")
        self.assertEqual(verdict.vote, "SUPPORT")

    def test_missing_vote_does_not_default_oppose(self):
        raw = json.dumps(
            {
                "core_reason": "reason exists",
                "main_risk": "risk exists",
                "question_for": "NO QUESTIONS",
                "question": "NO QUESTIONS",
                "can_change_mind_if": "evidence",
                "confidence": 70,
            }
        )
        with self.assertRaises(ValueError):
            parse_verdict(MELCHIOR, raw, "test-model")

    def test_empty_vote_does_not_default_oppose(self):
        with self.assertRaises(ValueError):
            parse_verdict(MELCHIOR, valid_verdict_raw(""), "test-model")

    def test_invalid_vote_does_not_default_oppose(self):
        with self.assertRaises(ValueError):
            parse_verdict(MELCHIOR, valid_verdict_raw("MAYBE"), "test-model")


class TestStrictReflectionVoteValidation(unittest.TestCase):
    def _verdict(self):
        return parse_verdict(MELCHIOR, valid_verdict_raw("OPPOSE"), "test-model")

    def test_valid_reflection_support_vote_parses(self):
        reflection = parse_reflection(
            MELCHIOR,
            self._verdict(),
            valid_reflection_raw("SUPPORT"),
            "test-model",
        )
        self.assertEqual(reflection.vote_after, "SUPPORT")

    def test_valid_reflection_oppose_vote_parses(self):
        reflection = parse_reflection(
            MELCHIOR,
            self._verdict(),
            valid_reflection_raw("OPPOSE"),
            "test-model",
        )
        self.assertEqual(reflection.vote_after, "OPPOSE")

    def test_missing_reflection_vote_does_not_preserve_previous_vote(self):
        raw = json.dumps(
            {
                "learned": "something",
                "reason": "some reason",
                "confidence_after_reflection": 65,
            }
        )
        with self.assertRaises(ValueError):
            parse_reflection(MELCHIOR, self._verdict(), raw, "test-model")

    def test_empty_reflection_vote_does_not_preserve_previous_vote(self):
        with self.assertRaises(ValueError):
            parse_reflection(MELCHIOR, self._verdict(), valid_reflection_raw(""), "test-model")

    def test_invalid_reflection_vote_does_not_preserve_previous_vote(self):
        with self.assertRaises(ValueError):
            parse_reflection(MELCHIOR, self._verdict(), valid_reflection_raw("MAYBE"), "test-model")


if __name__ == "__main__":
    unittest.main()
