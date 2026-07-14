"""Tests for the reflection refutation gate (anti-sycophancy)."""

import unittest

from magi.protocol.engine import REFLECTION_INSTRUCTION, MagiEngine


class TestReflectionGate(unittest.TestCase):
    def test_reflection_prompt_has_refutation_gate(self):
        text = REFLECTION_INSTRUCTION.lower()
        self.assertIn("did it defeat your core reason", text)
        self.assertIn("is not a defeater", text)
        self.assertIn("social agreement is not evidence", text)

    def test_reflection_prompt_anchors_to_members_own_condition(self):
        # The member's Round-1 can_change_mind_if must be injected as the bar.
        self.assertIn("{change_condition}", REFLECTION_INSTRUCTION)
        self.assertIn("the specific condition you named above", REFLECTION_INSTRUCTION)

    def test_reflection_prompt_forbids_folding_to_consensus(self):
        self.assertIn(
            "Do not abandon your facet because the rest of the council disagreed",
            REFLECTION_INSTRUCTION,
        )

    def test_reflection_prompt_preserves_prior_guarantees(self):
        # Guarantees the earlier prompt-quality tests depend on must survive.
        for phrase in [
            "Change your vote only if",
            "Adjust confidence realistically",
            "must not contradict each other",
            "Do not increase confidence",
        ]:
            self.assertIn(phrase, REFLECTION_INSTRUCTION)

    def test_reflection_still_runs_end_to_end_under_mock(self):
        engine = MagiEngine(mock=True)
        result = engine.deliberate("Should MAGI preserve minority reports?")
        self.assertEqual(len(result["reflections"]), 4)


if __name__ == "__main__":
    unittest.main()
