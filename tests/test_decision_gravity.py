"""Tests for decision gravity: the agreement bar scales with stakes.

The defining property: the SAME vote split yields DIFFERENT decisions as stakes
rise. Gravity only ever raises the bar — it can never turn a NO CONSENSUS into a
decision the base quorum would have refused.
"""

import unittest

from magi.protocol.engine import _decision_from_split, decide_reflections
from magi.protocol.gravity import (
    GRAVE,
    ROUTINE,
    SERIOUS,
    normalize_stakes,
    rule_for,
)
from magi.protocol.reflection import Reflection


def _reflections(support=0, oppose=0, abstain=0, invalid=0):
    out = []
    specs = [("SUPPORT", support), ("OPPOSE", oppose),
             ("ABSTAIN", abstain), ("INVALID_QUESTION", invalid)]
    for vote, n in specs:
        for _ in range(n):
            out.append(Reflection(
                member_name="M", member_title="t",
                vote_before=vote, vote_after=vote,
                confidence_before=80, confidence_after=80,
                learned="x", reason="y", model="m", raw="{}",
            ))
    return out


class TestStakesChangeTheOutcome(unittest.TestCase):
    def test_three_one_split_passes_routine_but_not_serious(self):
        # 3 SUPPORT / 1 OPPOSE: a clear majority with one dissenter.
        self.assertEqual(_decision_from_split(3, 1, 0, 0, ROUTINE), "SUPPORT")
        # SERIOUS forbids dissent among those who took a position.
        self.assertEqual(_decision_from_split(3, 1, 0, 0, SERIOUS), "NO CONSENSUS")

    def test_four_zero_passes_all_levels(self):
        for stakes in (ROUTINE, SERIOUS, GRAVE):
            self.assertEqual(_decision_from_split(4, 0, 0, 0, stakes), "SUPPORT")

    def test_grave_blocks_on_any_abstention(self):
        # 3 SUPPORT / 1 ABSTAIN: fine for ROUTINE, blocked for GRAVE.
        self.assertEqual(_decision_from_split(3, 0, 1, 0, ROUTINE), "SUPPORT")
        self.assertEqual(_decision_from_split(3, 0, 1, 0, SERIOUS), "SUPPORT")
        self.assertEqual(_decision_from_split(3, 0, 1, 0, GRAVE), "NO CONSENSUS")

    def test_grave_requires_full_council(self):
        # Even unanimous-among-present fails GRAVE if not everyone weighed in.
        self.assertEqual(_decision_from_split(3, 0, 0, 1, GRAVE), "NO CONSENSUS")

    def test_serious_allows_unanimous_present_with_no_dissent(self):
        # 3 SUPPORT / 1 ABSTAIN has no dissent -> SERIOUS passes, GRAVE does not.
        self.assertEqual(_decision_from_split(3, 0, 1, 0, SERIOUS), "SUPPORT")


class TestGravityNeverLowersTheBar(unittest.TestCase):
    def test_below_quorum_is_no_consensus_at_every_level(self):
        # 1 SUPPORT / 3 ABSTAIN never clears base quorum, regardless of stakes.
        for stakes in (ROUTINE, SERIOUS, GRAVE):
            self.assertEqual(_decision_from_split(1, 0, 3, 0, stakes), "NO CONSENSUS")

    def test_tie_is_no_consensus_at_every_level(self):
        for stakes in (ROUTINE, SERIOUS, GRAVE):
            self.assertEqual(_decision_from_split(2, 2, 0, 0, stakes), "NO CONSENSUS")


class TestDecideReflectionsCarriesStakes(unittest.TestCase):
    def test_decision_dict_reports_stakes_and_note(self):
        result = decide_reflections(_reflections(support=3, oppose=1), stakes=SERIOUS)
        self.assertEqual(result["stakes"], SERIOUS)
        self.assertEqual(result["decision"], "NO CONSENSUS")
        self.assertIn("SERIOUS", result["gravity_note"])

    def test_default_stakes_is_routine_and_preserves_old_behavior(self):
        result = decide_reflections(_reflections(support=3, oppose=1))
        self.assertEqual(result["stakes"], ROUTINE)
        self.assertEqual(result["decision"], "SUPPORT")


class TestStakesNormalization(unittest.TestCase):
    def test_unknown_stakes_defaults_to_routine(self):
        self.assertEqual(normalize_stakes("catastrophic"), ROUTINE)
        self.assertEqual(normalize_stakes(None), ROUTINE)
        self.assertEqual(normalize_stakes("grave"), GRAVE)

    def test_rule_lookup_is_case_insensitive(self):
        self.assertTrue(rule_for("serious").forbid_dissent)
        self.assertTrue(rule_for("GRAVE").require_full_council_agreement)


if __name__ == "__main__":
    unittest.main()
