"""Tests for MAGI progress callbacks."""

import unittest

from magi.protocol.engine import MagiEngine


class TestProgressIndicators(unittest.TestCase):
    def test_progress_callback_receives_protocol_stages(self):
        messages = []

        engine = MagiEngine(
            mock=True,
            progress=messages.append,
        )

        engine.deliberate("Should MAGI preserve minority reports?")

        self.assertIn("Round 1/5 — independent analysis", messages)
        self.assertIn("Round 2/5 — cross-examination", messages)
        self.assertIn("Round 3/5 — satisfaction evaluation", messages)
        self.assertIn("Round 4/5 — reflection", messages)
        self.assertIn("Decision — tallying reflected votes", messages)
        self.assertIn("Round 5/5 — chair dossier", messages)


if __name__ == "__main__":
    unittest.main()
