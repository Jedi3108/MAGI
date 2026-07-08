"""Smoke tests for the MAGI council core."""

import unittest

from magi.protocol.engine import MagiEngine


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


if __name__ == "__main__":
    unittest.main()
