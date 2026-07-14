import unittest

from magi.council.verdict import ABSTAIN, NO_CONSENSUS, OPPOSE, SUPPORT
from magi.protocol.engine import decide_reflections
from magi.protocol.reflection import Reflection


def reflection(vote: str) -> Reflection:
    return Reflection(
        member_name="TEST",
        member_title="Tester",
        vote_before=vote,
        vote_after=vote,
        confidence_before=80 if vote != ABSTAIN else 0,
        confidence_after=80 if vote != ABSTAIN else 0,
        learned="test",
        reason="test",
        model="test",
        raw="{}",
    )


class TestDecisionQuorum(unittest.TestCase):
    def test_one_support_three_abstain_is_no_consensus(self):
        result = decide_reflections([
            reflection(SUPPORT),
            reflection(ABSTAIN),
            reflection(ABSTAIN),
            reflection(ABSTAIN),
        ])

        self.assertEqual(result["decision"], NO_CONSENSUS)

    def test_one_oppose_three_abstain_is_no_consensus(self):
        result = decide_reflections([
            reflection(OPPOSE),
            reflection(ABSTAIN),
            reflection(ABSTAIN),
            reflection(ABSTAIN),
        ])

        self.assertEqual(result["decision"], NO_CONSENSUS)

    def test_three_support_one_abstain_is_support(self):
        result = decide_reflections([
            reflection(SUPPORT),
            reflection(SUPPORT),
            reflection(SUPPORT),
            reflection(ABSTAIN),
        ])

        self.assertEqual(result["decision"], SUPPORT)

    def test_three_oppose_one_abstain_is_oppose(self):
        result = decide_reflections([
            reflection(OPPOSE),
            reflection(OPPOSE),
            reflection(OPPOSE),
            reflection(ABSTAIN),
        ])

        self.assertEqual(result["decision"], OPPOSE)


if __name__ == "__main__":
    unittest.main()
