"""Smoke tests for the MAGI council core."""

import unittest

from magi.protocol.engine import MagiEngine
from magi.protocol.examination import collect_questions


class TestCouncilCore(unittest.TestCase):
    def test_mock_council_returns_four_verdicts(self):
        engine = MagiEngine(mock=True)

        result = engine.deliberate("Should MAGI preserve minority reports?")

        self.assertEqual(
            result["proposition"],
            "Should MAGI preserve minority reports?",
        )
        self.assertEqual(len(result["verdicts"]), 4)
        self.assertIn(
            result["decision"]["decision"],
            {"AFFIRMATIVE", "NEGATIVE", "NO CONSENSUS"},
        )

    def test_each_verdict_has_structured_fields(self):
        engine = MagiEngine(mock=True)

        result = engine.deliberate("Should MAGI remain model-agnostic?")

        for verdict in result["verdicts"]:
            self.assertTrue(verdict.member_name)
            self.assertIn(verdict.vote, {"AFFIRMATIVE", "NEGATIVE"})
            self.assertGreaterEqual(verdict.confidence, 0)
            self.assertLessEqual(verdict.confidence, 100)
            self.assertTrue(verdict.core_reason)
            self.assertTrue(verdict.main_risk)
            self.assertTrue(verdict.can_change_mind_if)

    def test_cross_examination_answers_routed_questions(self):
        engine = MagiEngine(mock=True)

        result = engine.deliberate("Should MAGI preserve minority reports?")

        questions = collect_questions(result["verdicts"])

        self.assertEqual(len(result["questions"]), len(questions))
        self.assertEqual(len(result["answers"]), len(questions))

        for answer in result["answers"]:
            self.assertTrue(answer.asker_name)
            self.assertTrue(answer.target_name)
            self.assertTrue(answer.question)
            self.assertTrue(answer.answer)


if __name__ == "__main__":
    unittest.main()
