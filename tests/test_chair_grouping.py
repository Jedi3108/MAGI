"""Tests for explicit Chair vote grouping under ballot semantics."""

import unittest

from magi.chair.record import build_structured_chair_record
from magi.protocol.engine import CHAIR_INSTRUCTION
from magi.protocol.reflection import Reflection


def reflection(name, before, after):
    return Reflection(
        member_name=name,
        member_title="Tester",
        vote_before=before,
        vote_after=after,
        confidence_before=70,
        confidence_after=80,
        learned=f"{name} learned something",
        reason=f"{name} final reason",
        model="test-model",
    )


class TestChairGrouping(unittest.TestCase):
    def test_structured_record_groups_final_votes(self):
        record = build_structured_chair_record(
            [
                reflection("MELCHIOR", "ABSTAIN", "ABSTAIN"),
                reflection("BALTHASAR", "OPPOSE", "SUPPORT"),
                reflection("CASPER", "OPPOSE", "OPPOSE"),
                reflection("ARTABAN", "OPPOSE", "OPPOSE"),
            ]
        )

        self.assertIn("FINAL POSITION GROUPS", record)
        self.assertIn("SUPPORT: BALTHASAR", record)
        self.assertIn("OPPOSE: CASPER, ARTABAN", record)
        self.assertIn("ABSTAIN: MELCHIOR", record)
        self.assertIn("INVALID_QUESTION: None", record)

    def test_chair_instruction_forbids_cross_group_attribution(self):
        self.assertIn("majority_reasoning must summarize only SUPPORT members", CHAIR_INSTRUCTION)
        self.assertIn("majority_reasoning must summarize only OPPOSE members", CHAIR_INSTRUCTION)
        self.assertIn("Never place a SUPPORT member in OPPOSE reasoning", CHAIR_INSTRUCTION)
        self.assertIn("Treat ABSTAIN as uncertainty/insufficient information", CHAIR_INSTRUCTION)
        self.assertIn("Treat INVALID_QUESTION as rejection of the proposition framing", CHAIR_INSTRUCTION)


if __name__ == "__main__":
    unittest.main()
