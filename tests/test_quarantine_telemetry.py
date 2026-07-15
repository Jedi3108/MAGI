"""Tests for quarantine telemetry.

Error strings below are the real messages raised by magi/council/verdict.py and
the engine's semantic check, not invented examples.
"""

import unittest

from magi.tools import telemetry


class TestClassifier(unittest.TestCase):
    def test_polarity_blocklist_is_identified(self):
        self.assertEqual(
            telemetry.classify(
                "OPPOSE action_causality contains SUPPORT-polarity language: 'acting decisively'"
            ),
            ("action_causality", "polarity_blocklist"),
        )

    def test_prefix_mismatch_is_identified(self):
        self.assertEqual(
            telemetry.classify(
                "Action causality contradicts vote 'SUPPORT': expected prefix "
                "'IF THE TARGET ACTION IS TAKEN, THEN IT HELPS BECAUSE', got 'this helps'"
            ),
            ("action_causality", "prefix_mismatch"),
        )

    def test_prefix_empty_is_identified(self):
        self.assertEqual(
            telemetry.classify(
                "vote_reason_alignment has no meaningful reason after prefix: 'I SUPPORT'"
            ),
            ("vote_reason_alignment", "prefix_empty"),
        )

    def test_inaction_language_is_identified(self):
        field, kind = telemetry.classify(
            "OPPOSE action_causality must describe harm from taking the target action, "
            "not harm from inaction: 'if no action is taken humans die'"
        )
        self.assertEqual(field, "action_causality")
        self.assertEqual(kind, "inaction_language")

    def test_semantic_check_is_identified(self):
        self.assertEqual(
            telemetry.classify(
                "Semantic vote check contradicted OPPOSE: the reasoning supports "
                "taking the target action."
            ),
            ("semantic_check", "reasoning_inverted"),
        )

    def test_invalid_vote_token_is_identified(self):
        self.assertEqual(
            telemetry.classify("Invalid vote token: 'YES'"),
            ("vote", "invalid_vote_token"),
        )

    def test_stance_summary_prefix_is_identified(self):
        field, kind = telemetry.classify(
            "Stance summary contradicts vote 'OPPOSE': expected prefix 'I OPPOSE', got 'I think'"
        )
        self.assertEqual(field, "stance_summary")
        self.assertEqual(kind, "prefix_mismatch")

    def test_counterfactual_is_not_shadowed_by_action_causality(self):
        field, _ = telemetry.classify(
            "OPPOSE counterfactual_comparison must compare taking the action as worse, "
            "not describe harm from inaction: 'x'"
        )
        self.assertEqual(field, "counterfactual_comparison")


class TestCounters(unittest.TestCase):
    def setUp(self):
        telemetry.reset()

    def test_reset_clears_everything(self):
        telemetry.record_failure("CASPER", "Invalid vote token: 'YES'")
        telemetry.reset()
        self.assertEqual(telemetry.snapshot().total_failures, 0)

    def test_failure_and_quarantine_are_counted_separately(self):
        err = "Invalid vote token: 'YES'"
        telemetry.record_failure("CASPER", err)
        telemetry.record_failure("CASPER", err)
        telemetry.record_quarantine("CASPER", err)

        snap = telemetry.snapshot()
        self.assertEqual(snap.total_failures, 2)
        self.assertEqual(snap.total_quarantines, 1)
        self.assertEqual(snap.quarantines_by_member["CASPER"], 1)

    def test_repair_success_rate(self):
        telemetry.record_repair_attempt("MELCHIOR")
        telemetry.record_repair_attempt("MELCHIOR")
        telemetry.record_repair_success("MELCHIOR")
        self.assertEqual(telemetry.snapshot().repair_success_rate, 0.5)

    def test_repair_rate_is_zero_when_never_attempted(self):
        self.assertEqual(telemetry.snapshot().repair_success_rate, 0.0)

    def test_top_killer_reports_the_deadliest_cause(self):
        telemetry.record_quarantine("CASPER", "Invalid vote token: 'YES'")
        for _ in range(3):
            telemetry.record_quarantine(
                "ARTABAN",
                "Action causality contradicts vote 'SUPPORT': expected prefix 'X', got 'y'",
            )
        (field, kind), n = telemetry.snapshot().top_killers(1)[0]
        self.assertEqual((field, kind), ("action_causality", "prefix_mismatch"))
        self.assertEqual(n, 3)


if __name__ == "__main__":
    unittest.main()
