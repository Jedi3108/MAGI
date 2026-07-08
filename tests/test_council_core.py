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
        self.assertEqual(len(result["reflections"]), 4)
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

    def test_satisfaction_evaluations_match_answers(self):
        engine = MagiEngine(mock=True)

        result = engine.deliberate("Should MAGI preserve minority reports?")

        self.assertEqual(len(result["evaluations"]), len(result["answers"]))

        for evaluation in result["evaluations"]:
            self.assertTrue(evaluation.asker_name)
            self.assertTrue(evaluation.target_name)
            self.assertTrue(evaluation.question)
            self.assertTrue(evaluation.answer)
            self.assertIn(
                evaluation.satisfaction,
                {"SATISFIED", "PARTIALLY SATISFIED", "NOT SATISFIED"},
            )
            self.assertGreaterEqual(evaluation.confidence_delta, -100)
            self.assertLessEqual(evaluation.confidence_delta, 100)

    def test_reflections_update_or_preserve_member_positions(self):
        engine = MagiEngine(mock=True)

        result = engine.deliberate("Should MAGI preserve minority reports?")

        self.assertEqual(len(result["reflections"]), 4)

        for reflection in result["reflections"]:
            self.assertTrue(reflection.member_name)
            self.assertIn(reflection.vote_before, {"AFFIRMATIVE", "NEGATIVE"})
            self.assertIn(reflection.vote_after, {"AFFIRMATIVE", "NEGATIVE"})
            self.assertGreaterEqual(reflection.confidence_before, 0)
            self.assertLessEqual(reflection.confidence_before, 100)
            self.assertGreaterEqual(reflection.confidence_after, 0)
            self.assertLessEqual(reflection.confidence_after, 100)
            self.assertTrue(reflection.learned)
            self.assertTrue(reflection.reason)

    def test_chair_dossier_exists_and_summarizes_decision(self):
        engine = MagiEngine(mock=True)

        result = engine.deliberate("Should MAGI preserve minority reports?")
        dossier = result["dossier"]

        self.assertIn(
            dossier.decision,
            {"AFFIRMATIVE", "NEGATIVE", "NO CONSENSUS"},
        )
        self.assertTrue(dossier.vote_split)
        self.assertTrue(dossier.majority_reasoning)
        self.assertTrue(dossier.minority_reasoning)
        self.assertTrue(dossier.key_risks)
        self.assertTrue(dossier.outstanding_uncertainties)
        self.assertTrue(dossier.required_conditions)
        self.assertTrue(dossier.recommended_next_action)


if __name__ == "__main__":
    unittest.main()
