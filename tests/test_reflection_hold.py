"""Tests for reflection hold/change validation.

Observed bug: a member that HELD its Round-1 vote while writing a learning-focused
reflection reason was rejected and frozen at its entry confidence, because the
validator applied the same "reason must be directional" test to holds as to flips.
MELCHIOR and BALTHASAR were frozen at 85; CASPER passed only because her reason
happened to be explicitly directional.

A held vote was already validated in Round 1. It should be accepted (carrying the
member's own updated confidence) unless the reason positively argues the OPPOSITE
direction. A changed vote must still be gated strictly.
"""

import unittest

from magi.council.members import MELCHIOR
from magi.council.verdict import SUPPORT, OPPOSE, Verdict
from magi.protocol.engine import MagiEngine
from magi.protocol.reflection import Reflection


def _verdict(vote, confidence, target="preserve minority reports"):
    return Verdict(
        member_name="MELCHIOR", member_title="The Scientist",
        vote=vote, confidence=confidence,
        target_action=target, stance_summary=f"I {vote}",
        vote_reason_alignment=f"I {vote} THE TARGET ACTION BECAUSE x",
        action_causality="IF THE TARGET ACTION IS TAKEN, THEN IT HELPS BECAUSE x",
        counterfactual_comparison="TAKING THE TARGET ACTION IS BETTER THAN NOT TAKING IT BECAUSE x",
        core_reason="x", main_risk="y",
        question_for="NO QUESTIONS", question="NO QUESTIONS",
        can_change_mind_if="new evidence", raw="{}", model="qwen2.5",
    )


def _reflection(vote_after, conf_after, reason):
    return Reflection(
        member_name="MELCHIOR", member_title="The Scientist",
        vote_before=SUPPORT, vote_after=vote_after,
        confidence_before=85, confidence_after=conf_after,
        learned="something", reason=reason, model="qwen2.5", raw="{}",
    )


class _Engine(MagiEngine):
    """MagiEngine with the semantic checker stubbed to a fixed relation."""
    def __init__(self, forced_relation):
        self.mock = False
        self._forced = forced_relation
    def _semantic_text_relation(self, target_action, text, model):
        return self._forced


class TestHeldVotes(unittest.TestCase):
    def test_held_support_with_learning_reason_is_accepted(self):
        # This is the MELCHIOR case: held SUPPORT, non-directional reason -> UNCLEAR.
        engine = _Engine("UNCLEAR")
        v = _verdict(SUPPORT, 85)
        r = _reflection(SUPPORT, 90, "The council deepened my understanding of the value.")
        out = engine._validated_reflection(v, r, "qwen2.5")
        self.assertEqual(out.vote_after, SUPPORT)
        self.assertEqual(out.confidence_after, 90)  # member's own confidence, not frozen 85
        self.assertNotIn("did not semantically support", out.reason)

    def test_held_support_carries_raised_confidence(self):
        engine = _Engine("UNCLEAR")
        v = _verdict(SUPPORT, 95)
        r = _reflection(SUPPORT, 100, "still stands")
        self.assertEqual(engine._validated_reflection(v, r, "qwen2.5").confidence_after, 100)

    def test_held_vote_rejected_only_if_reason_argues_opposite(self):
        # Held SUPPORT but the reason actually argues NOT-TAKING: latent inversion.
        engine = _Engine("SUPPORTS_NOT_TAKING")
        v = _verdict(SUPPORT, 85)
        r = _reflection(SUPPORT, 90, "actually this would cause real harm")
        out = engine._validated_reflection(v, r, "qwen2.5")
        self.assertEqual(out.confidence_after, 85)  # preserved
        self.assertIn("argued against the held vote", out.reason)


class TestChangedVotes(unittest.TestCase):
    def test_flip_accepted_when_reason_supports_new_direction(self):
        engine = _Engine("SUPPORTS_NOT_TAKING")
        v = _verdict(SUPPORT, 85)
        r = _reflection(OPPOSE, 70, "the debate showed the harm outweighs the benefit")
        out = engine._validated_reflection(v, r, "qwen2.5")
        self.assertEqual(out.vote_after, OPPOSE)
        self.assertEqual(out.confidence_after, 70)

    def test_flip_rejected_when_reason_does_not_support_new_direction(self):
        # Flip to OPPOSE but reason is unclear/still supportive -> gate holds.
        engine = _Engine("UNCLEAR")
        v = _verdict(SUPPORT, 85)
        r = _reflection(OPPOSE, 70, "I learned some things")
        out = engine._validated_reflection(v, r, "qwen2.5")
        self.assertEqual(out.vote_after, SUPPORT)  # preserved
        self.assertIn("did not semantically support the changed vote", out.reason)


if __name__ == "__main__":
    unittest.main()
