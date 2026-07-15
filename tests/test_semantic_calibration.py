"""Tests for the semantic checker calibration harness."""

import unittest

from magi.tools.semantic_calibration import (
    CALIBRATION_CASES,
    SUPPORTS_NOT_TAKING,
    SUPPORTS_TAKING,
    UNCLEAR,
    CalibrationReport,
    Case,
    CaseResult,
    run_calibration,
)


def _r(expected, answers):
    return CaseResult(
        case=Case(target_action="a", text="t", expected=expected),
        answers=list(answers),
    )


class TestCaseSet(unittest.TestCase):
    def test_cases_cover_all_three_relations(self):
        expected = {c.expected for c in CALIBRATION_CASES}
        self.assertEqual(expected, {SUPPORTS_TAKING, SUPPORTS_NOT_TAKING, UNCLEAR})

    def test_directional_cases_are_balanced(self):
        take = sum(1 for c in CALIBRATION_CASES if c.expected == SUPPORTS_TAKING)
        nottake = sum(1 for c in CALIBRATION_CASES if c.expected == SUPPORTS_NOT_TAKING)
        # An unbalanced set would let a constant-answer checker score well.
        self.assertEqual(take, nottake)


class TestMetrics(unittest.TestCase):
    def test_perfect_case(self):
        r = _r(SUPPORTS_TAKING, [SUPPORTS_TAKING] * 5)
        self.assertEqual(r.accuracy, 1.0)
        self.assertEqual(r.consistency, 1.0)
        self.assertTrue(r.is_correct)

    def test_coin_flip_is_detected_as_inconsistent(self):
        r = _r(SUPPORTS_TAKING, [SUPPORTS_TAKING, SUPPORTS_NOT_TAKING] * 2)
        self.assertEqual(r.accuracy, 0.5)
        self.assertEqual(r.consistency, 0.5)

    def test_consistently_wrong_scores_high_consistency_low_accuracy(self):
        r = _r(SUPPORTS_TAKING, [SUPPORTS_NOT_TAKING] * 5)
        self.assertEqual(r.consistency, 1.0)
        self.assertEqual(r.accuracy, 0.0)
        self.assertFalse(r.is_correct)

    def test_unclear_rate_counts_punts(self):
        report = CalibrationReport(
            repetitions=2,
            results=[_r(SUPPORTS_TAKING, [SUPPORTS_TAKING, UNCLEAR])],
        )
        self.assertEqual(report.unclear_rate, 0.5)

    def test_decisive_accuracy_ignores_unclear_cases(self):
        report = CalibrationReport(
            repetitions=1,
            results=[
                _r(SUPPORTS_TAKING, [SUPPORTS_TAKING]),   # correct, directional
                _r(UNCLEAR, [SUPPORTS_TAKING]),           # wrong, but cannot quarantine
            ],
        )
        self.assertEqual(report.decisive_accuracy(), 1.0)

    def test_harmful_inversions_only_flags_opposite_direction(self):
        report = CalibrationReport(
            repetitions=1,
            results=[
                _r(SUPPORTS_TAKING, [SUPPORTS_NOT_TAKING]),  # inversion
                _r(SUPPORTS_TAKING, [UNCLEAR]),              # punt, not harmful
            ],
        )
        self.assertEqual(len(report.harmful_inversions()), 1)

    def test_confusion_counts_every_run(self):
        report = CalibrationReport(
            repetitions=2,
            results=[_r(SUPPORTS_TAKING, [SUPPORTS_TAKING, SUPPORTS_NOT_TAKING])],
        )
        conf = report.confusion()
        self.assertEqual(conf[(SUPPORTS_TAKING, SUPPORTS_TAKING)], 1)
        self.assertEqual(conf[(SUPPORTS_TAKING, SUPPORTS_NOT_TAKING)], 1)


class TestHarnessWiring(unittest.TestCase):
    def test_run_calibration_records_every_repetition(self):
        class FakeEngine:
            def _semantic_text_relation(self, target_action, text, model):
                return SUPPORTS_TAKING

        cases = (Case(target_action="a", text="t", expected=SUPPORTS_TAKING),)
        report = run_calibration(FakeEngine(), "m", cases=cases, repetitions=4)
        self.assertEqual(len(report.results[0].answers), 4)
        self.assertEqual(report.accuracy, 1.0)


if __name__ == "__main__":
    unittest.main()
