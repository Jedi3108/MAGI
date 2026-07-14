"""Tests that reasoning is generated BEFORE the vote token.

Background: with "vote" as the first key in the JSON schema, the model emitted a
vote before any reasoning existed in context. The vote was therefore drawn from
the base model's prior rather than from the facet's argument, and the prose that
followed was post-hoc rationalisation. Measured effect: 100/100 votes OPPOSE
across five propositions of differing valence, with reasoning that frequently
argued the opposite of the vote cast.

These tests lock the ordering: every decision field must come after the reasoning
that is supposed to justify it.
"""

import unittest

from magi.protocol.engine import (
    EVALUATION_INSTRUCTION,
    JUDGE_INSTRUCTION,
    REFLECTION_INSTRUCTION,
)


class TestJudgeReasonsBeforeVoting(unittest.TestCase):
    def test_core_reason_precedes_vote(self):
        self.assertLess(
            JUDGE_INSTRUCTION.index('"core_reason":'),
            JUDGE_INSTRUCTION.index('"vote":'),
        )

    def test_all_reasoning_fields_precede_vote(self):
        vote_at = JUDGE_INSTRUCTION.index('"vote":')
        for field in ('"main_risk":', '"question":', '"can_change_mind_if":'):
            self.assertLess(JUDGE_INSTRUCTION.index(field), vote_at, field)

    def test_confidence_follows_vote(self):
        self.assertLess(
            JUDGE_INSTRUCTION.index('"vote":'),
            JUDGE_INSTRUCTION.index('"confidence":'),
        )

    def test_judge_states_vote_must_follow_reason(self):
        self.assertIn("must follow from", JUDGE_INSTRUCTION)


class TestReflectionReasonsBeforeVoting(unittest.TestCase):
    def test_reason_precedes_vote(self):
        self.assertLess(
            REFLECTION_INSTRUCTION.index('"reason":'),
            REFLECTION_INSTRUCTION.index('"vote_after_reflection":'),
        )

    def test_learned_precedes_reason(self):
        self.assertLess(
            REFLECTION_INSTRUCTION.index('"learned":'),
            REFLECTION_INSTRUCTION.index('"reason":'),
        )


class TestEvaluationReasonsBeforeRating(unittest.TestCase):
    def test_reason_precedes_satisfaction(self):
        self.assertLess(
            EVALUATION_INSTRUCTION.index('"reason":'),
            EVALUATION_INSTRUCTION.index('"satisfaction":'),
        )


class TestParsingIsOrderIndependent(unittest.TestCase):
    """Parsers read by key, so reordering the schema must not affect them."""

    def test_verdict_parses_with_vote_last(self):
        import json

        from magi.council.members import MELCHIOR
        from magi.council.verdict import parse_verdict

        raw = json.dumps(
            {
                "core_reason": "evidence is insufficient",
                "main_risk": "a bad call",
                "question_for": "CASPER",
                "question": "what is fragile?",
                "can_change_mind_if": "new data",
                "stance_summary": "I SUPPORT the action.",
                "vote_reason_alignment": "I SUPPORT THE TARGET ACTION BECAUSE the reason supports the action.",
                "action_causality": "IF THE TARGET ACTION IS TAKEN, THEN IT HELPS BECAUSE the reason supports the action.",
                "counterfactual_comparison": "TAKING THE TARGET ACTION IS BETTER THAN NOT TAKING IT BECAUSE the reason supports action.",
                "vote": "SUPPORT",
                "confidence": 77,
            }
        )
        verdict = parse_verdict(MELCHIOR, raw, "test-model")
        self.assertEqual(verdict.vote, "SUPPORT")
        self.assertEqual(verdict.confidence, 77)
        self.assertEqual(verdict.core_reason, "evidence is insufficient")


if __name__ == "__main__":
    unittest.main()
