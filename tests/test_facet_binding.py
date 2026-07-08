"""Tests for facet binding: the properties that keep four voices from collapsing into one."""

import unittest

from magi.council.members import CHAIR_SAMPLING, COUNCIL
from magi.protocol.engine import JUDGE_INSTRUCTION


class TestSamplingProfiles(unittest.TestCase):
    def test_every_member_and_chair_have_valid_sampling(self):
        for s in [m.sampling for m in COUNCIL] + [CHAIR_SAMPLING]:
            self.assertGreater(s.temperature, 0.0)
            self.assertLessEqual(s.temperature, 2.0)
            self.assertGreater(s.top_p, 0.0)
            self.assertLessEqual(s.top_p, 1.0)

    def test_temperaments_are_spread_not_uniform(self):
        temps = [m.sampling.temperature for m in COUNCIL]
        # The whole point: members must NOT all sample identically.
        self.assertGreaterEqual(len(set(temps)), 3)

    def test_scientist_is_colder_than_intuitive(self):
        by_name = {m.name: m for m in COUNCIL}
        # Precision vs intuition, made mechanical.
        self.assertLess(
            by_name["MELCHIOR"].sampling.temperature,
            by_name["CASPER"].sampling.temperature,
        )


class TestJudgePromptBindsFacet(unittest.TestCase):
    def test_judge_prompt_does_not_leak_all_facets_to_every_member(self):
        # The old prompt listed every member's charge to every member, which
        # invited averaging. Independent analysis must not do this.
        self.assertNotIn("BALTHASAR cares about", JUDGE_INSTRUCTION)
        self.assertNotIn("CASPER cares about", JUDGE_INSTRUCTION)

    def test_judge_prompt_forbids_the_agreeable_middle(self):
        text = JUDGE_INSTRUCTION.lower()
        self.assertIn("follow your facet", text)
        self.assertIn("do not try to be balanced", text)


if __name__ == "__main__":
    unittest.main()
