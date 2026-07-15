"""Tests for the independence probe metrics.

The metric tests use synthetic samples with known votes so correctness does not
depend on mock randomness.
"""

import unittest

from magi.tools.independence import (
    abstain_rate,
    decisive_agreement,
    PHASE_ROUND1,
    Sample,
    support_rate,
    convergence,
    mean_confidence,
    member_stability,
    pairwise_agreement,
    run_probe,
)
from magi.protocol.engine import MagiEngine

MEMBERS = ["MELCHIOR", "BALTHASAR", "CASPER", "ARTABAN"]


def _s(prop, rep, votes, conf=None):
    conf = conf or {m: 70 for m in votes}
    return Sample(proposition=prop, repetition=rep, round1_votes=votes, round1_conf=conf)


class TestMetrics(unittest.TestCase):
    def test_agreement_identical_voters_is_one(self):
        samples = [
            _s("p", 0, {"MELCHIOR": "SUPPORT", "BALTHASAR": "SUPPORT"}),
            _s("p", 1, {"MELCHIOR": "OPPOSE", "BALTHASAR": "OPPOSE"}),
        ]
        agree = pairwise_agreement(samples, ["MELCHIOR", "BALTHASAR"])
        self.assertEqual(agree[("BALTHASAR", "MELCHIOR")], 1.0)

    def test_agreement_opposite_voters_is_zero(self):
        samples = [
            _s("p", 0, {"MELCHIOR": "SUPPORT", "CASPER": "OPPOSE"}),
            _s("p", 1, {"MELCHIOR": "OPPOSE", "CASPER": "SUPPORT"}),
        ]
        agree = pairwise_agreement(samples, ["MELCHIOR", "CASPER"])
        self.assertEqual(agree[("CASPER", "MELCHIOR")], 0.0)

    def test_stability_perfect_when_consistent(self):
        samples = [_s("p", r, {"CASPER": "SUPPORT"}) for r in range(5)]
        stab = member_stability(samples, ["CASPER"])
        self.assertEqual(stab["CASPER"], 1.0)

    def test_stability_half_on_coin_flip(self):
        votes = ["SUPPORT", "OPPOSE", "SUPPORT", "OPPOSE"]
        samples = [_s("p", r, {"CASPER": v}) for r, v in enumerate(votes)]
        stab = member_stability(samples, ["CASPER"])
        self.assertEqual(stab["CASPER"], 0.5)

    def test_stability_averages_across_propositions(self):
        samples = [
            _s("p1", 0, {"CASPER": "SUPPORT"}),
            _s("p1", 1, {"CASPER": "SUPPORT"}),  # p1 stability 1.0
            _s("p2", 0, {"CASPER": "SUPPORT"}),
            _s("p2", 1, {"CASPER": "OPPOSE"}),      # p2 stability 0.5
        ]
        stab = member_stability(samples, ["CASPER"])
        self.assertAlmostEqual(stab["CASPER"], 0.75)

    def test_support_rate(self):
        samples = [
            _s("p", 0, {"ARTABAN": "SUPPORT"}),
            _s("p", 1, {"ARTABAN": "OPPOSE"}),
            _s("p", 2, {"ARTABAN": "OPPOSE"}),
            _s("p", 3, {"ARTABAN": "OPPOSE"}),
        ]
        self.assertEqual(support_rate(samples, ["ARTABAN"])["ARTABAN"], 0.25)

    def test_mean_confidence(self):
        samples = [
            _s("p", 0, {"MELCHIOR": "SUPPORT"}, conf={"MELCHIOR": 60}),
            _s("p", 1, {"MELCHIOR": "SUPPORT"}, conf={"MELCHIOR": 80}),
        ]
        self.assertEqual(mean_confidence(samples, ["MELCHIOR"])["MELCHIOR"], 70.0)

    def test_convergence_none_without_reflected_votes(self):
        samples = [_s("p", 0, {"MELCHIOR": "SUPPORT"})]
        self.assertIsNone(convergence(samples, ["MELCHIOR"]))

    def test_convergence_positive_when_reflection_aligns(self):
        s = Sample(
            proposition="p", repetition=0,
            round1_votes={"MELCHIOR": "SUPPORT", "CASPER": "OPPOSE"},
            round1_conf={"MELCHIOR": 70, "CASPER": 70},
            reflected_votes={"MELCHIOR": "SUPPORT", "CASPER": "SUPPORT"},
            reflected_conf={"MELCHIOR": 70, "CASPER": 70},
        )
        # before: disagree (0.0); after: agree (1.0) -> convergence +1.0
        self.assertEqual(convergence([s], ["MELCHIOR", "CASPER"]), 1.0)


class TestProbeRunsUnderMock(unittest.TestCase):
    def test_probe_produces_samples_for_every_prop_and_rep(self):
        engine = MagiEngine(mock=True)
        report = run_probe(engine, ["p1", "p2"], repetitions=3)
        self.assertEqual(len(report.samples), 6)
        for sample in report.samples:
            self.assertEqual(set(sample.round1_votes), set(MEMBERS))

    def test_full_mode_captures_reflected_votes(self):
        engine = MagiEngine(mock=True)
        report = run_probe(engine, ["p1"], repetitions=1, full=True)
        self.assertTrue(report.full)
        self.assertEqual(set(report.samples[0].reflected_votes), set(MEMBERS))


if __name__ == "__main__":
    unittest.main()


class TestBallotVocabularyMigration(unittest.TestCase):
    """The probe was written for a binary vote. These lock the 4-valued ballot."""

    def test_stability_does_not_conflate_oppose_with_abstain(self):
        casts = ["OPPOSE", "ABSTAIN", "OPPOSE", "ABSTAIN", "ABSTAIN"]
        samples = [
            _s("p", i, {"CASPER": v}) for i, v in enumerate(casts)
        ]
        # Modal vote is ABSTAIN (3/5). Must NOT report 1.0.
        self.assertAlmostEqual(member_stability(samples, ["CASPER"])["CASPER"], 0.6)

    def test_decisive_agreement_ignores_quarantined_ballots(self):
        samples = [
            _s("p", 0, {"MELCHIOR": "ABSTAIN", "CASPER": "ABSTAIN"}),
            _s("p", 1, {"MELCHIOR": "SUPPORT", "CASPER": "OPPOSE"}),
        ]
        agree, n = decisive_agreement(samples, ["MELCHIOR", "CASPER"])[("CASPER", "MELCHIOR")]
        # Only one sample had two real positions, and they disagreed.
        self.assertEqual(n, 1)
        self.assertEqual(agree, 0.0)

    def test_two_quarantined_members_are_not_counted_as_agreeing(self):
        samples = [_s("p", 0, {"MELCHIOR": "ABSTAIN", "CASPER": "ABSTAIN"})]
        agree, n = decisive_agreement(samples, ["MELCHIOR", "CASPER"])[("CASPER", "MELCHIOR")]
        self.assertEqual(n, 0)

    def test_abstain_rate_counts_non_positions(self):
        casts = ["SUPPORT", "ABSTAIN", "OPPOSE", "INVALID_QUESTION"]
        samples = [_s("p", i, {"ARTABAN": v}) for i, v in enumerate(casts)]
        self.assertEqual(abstain_rate(samples, ["ARTABAN"])["ARTABAN"], 0.5)
