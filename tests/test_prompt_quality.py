"""Tests for prompt quality constraints."""

import unittest

from magi.council.members import COUNCIL
from magi.protocol.engine import (
    ANSWER_INSTRUCTION,
    CHAIR_INSTRUCTION,
    EVALUATION_INSTRUCTION,
    JUDGE_INSTRUCTION,
    REFLECTION_INSTRUCTION,
)


class TestPromptQuality(unittest.TestCase):
    def test_council_personas_are_distinct(self):
        personas = [member.persona for member in COUNCIL]

        for member in COUNCIL:
            self.assertIn(member.name, member.persona)
            self.assertIn(member.title, member.persona)
            self.assertTrue(member.facet)

        self.assertEqual(len(set(personas)), len(personas))

    def test_judge_prompt_discourages_generic_answers(self):
        self.assertIn("Do not give a generic assistant answer", JUDGE_INSTRUCTION)
        self.assertIn("Confidence calibration", JUDGE_INSTRUCTION)
        self.assertIn("Disagreement is allowed", JUDGE_INSTRUCTION)

    def test_answer_prompt_demands_direct_answers(self):
        self.assertIn("Answer the actual question", ANSWER_INSTRUCTION)
        self.assertIn("If the asker raised a valid concern", ANSWER_INSTRUCTION)

    def test_evaluation_prompt_requires_unresolved_concerns(self):
        self.assertIn("what remains unresolved", EVALUATION_INSTRUCTION)
        self.assertIn("Confidence deltas should usually be modest", EVALUATION_INSTRUCTION)

    def test_reflection_prompt_discourages_unjustified_vote_changes(self):
        self.assertIn("Change your vote only if", REFLECTION_INSTRUCTION)
        self.assertIn("Adjust confidence realistically", REFLECTION_INSTRUCTION)


    def test_reflection_prompt_requires_internal_consistency(self):
        self.assertIn("must not contradict each other", REFLECTION_INSTRUCTION)
        self.assertIn("Do not increase confidence", REFLECTION_INSTRUCTION)



    def test_chair_prompt_receives_structured_final_vote_record(self):
        self.assertIn("Authoritative final reflected vote record", CHAIR_INSTRUCTION)
        self.assertIn("overrides the transcript", CHAIR_INSTRUCTION)
        self.assertIn("Base vote attribution on the authoritative final reflected vote record", CHAIR_INSTRUCTION)

    def test_chair_prompt_uses_final_reflected_votes(self):
        self.assertIn("final reflected votes are authoritative", CHAIR_INSTRUCTION)
        self.assertIn("Do not treat Round 1 votes", CHAIR_INSTRUCTION)
        self.assertIn("Do not attribute SUPPORT reasoning", CHAIR_INSTRUCTION)

    def test_chair_prompt_handles_no_consensus(self):
        self.assertIn("If the decision is NO CONSENSUS", CHAIR_INSTRUCTION)
        self.assertIn("no majority exists", CHAIR_INSTRUCTION)

    def test_chair_prompt_prevents_invented_arguments(self):
        self.assertIn("You do not invent arguments", CHAIR_INSTRUCTION)
        self.assertIn("Recommended next action must be concrete", CHAIR_INSTRUCTION)


if __name__ == "__main__":
    unittest.main()
