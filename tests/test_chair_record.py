"""Tests for structured Chair records."""

import unittest

from magi.chair.record import build_structured_chair_record
from magi.protocol.reflection import Reflection


class TestStructuredChairRecord(unittest.TestCase):
    def test_structured_record_contains_authoritative_final_votes(self):
        reflections = [
            Reflection(
                member_name="MELCHIOR",
                member_title="The Scientist",
                vote_before="AFFIRMATIVE",
                vote_after="NEGATIVE",
                confidence_before=80,
                confidence_after=60,
                learned="The evidence was weaker than expected.",
                reason="Final reason favors rejection.",
                model="test",
            ),
            Reflection(
                member_name="CASPER",
                member_title="The Woman",
                vote_before="NEGATIVE",
                vote_after="AFFIRMATIVE",
                confidence_before=70,
                confidence_after=75,
                learned="A suppressed perspective matters.",
                reason="Final reason favors preservation.",
                model="test",
            ),
        ]

        record = build_structured_chair_record(reflections)

        self.assertIn("AUTHORITATIVE FINAL REFLECTED VOTE RECORD", record)
        self.assertIn("final_affirmative_count=1", record)
        self.assertIn("final_negative_count=1", record)
        self.assertIn("MELCHIOR", record)
        self.assertIn("final_vote=NEGATIVE", record)
        self.assertIn("round1_vote=AFFIRMATIVE", record)
        self.assertIn("CASPER", record)
        self.assertIn("final_vote=AFFIRMATIVE", record)

    def test_structured_record_collapses_multiline_text(self):
        reflections = [
            Reflection(
                member_name="ARTABAN",
                member_title="The Man",
                vote_before="NEGATIVE",
                vote_after="NEGATIVE",
                confidence_before=80,
                confidence_after=70,
                learned="Line one.\nLine two.",
                reason="Reason one.\nReason two.",
                model="test",
            ),
        ]

        record = build_structured_chair_record(reflections)

        self.assertIn("learned=Line one. Line two.", record)
        self.assertIn("final_reason=Reason one. Reason two.", record)


if __name__ == "__main__":
    unittest.main()
