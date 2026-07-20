"""Tests for the live NERV bridge.

The whole reason for polling over streaming: it is testable without a browser.
These drive real engine events through LiveState and hit the HTTP endpoints.
"""

import json
import threading
import unittest
import urllib.request

from magi.protocol.engine import MagiEngine
from magi.tools.live_bridge import LiveState, LIVE_BOARD_HTML, start_server


class TestLiveState(unittest.TestCase):
    def test_run_started_initializes_pending_units(self):
        s = LiveState()
        s.update({"type": "run_started", "proposition": "p", "stakes": "ROUTINE",
                  "members": ["MELCHIOR", "BALTHASAR", "CASPER", "ARTABAN"], "models": {}})
        snap = s.snapshot()
        self.assertEqual(snap["phase"], "running")
        self.assertEqual(len(snap["units"]), 4)
        self.assertTrue(all(u["status"] == "pending" for u in snap["units"].values()))

    def test_member_thinking_then_resolved(self):
        s = LiveState()
        s.update({"type": "run_started", "members": ["MELCHIOR"], "proposition": "p"})
        s.update({"type": "member_started", "member": "MELCHIOR"})
        self.assertEqual(s.snapshot()["units"]["MELCHIOR"]["status"], "thinking")
        s.update({"type": "member_resolved", "member": "MELCHIOR",
                  "vote": "SUPPORT", "confidence": 85, "reason": "r"})
        u = s.snapshot()["units"]["MELCHIOR"]
        self.assertEqual(u["status"], "resolved")
        self.assertEqual(u["vote"], "SUPPORT")
        self.assertEqual(u["confidence"], 85)

    def test_reflection_marks_changed(self):
        s = LiveState()
        s.update({"type": "run_started", "members": ["ARTABAN"], "proposition": "p"})
        s.update({"type": "reflection_resolved", "member": "ARTABAN",
                  "from": "SUPPORT", "to": "OPPOSE", "confidence": 70, "reason": "moved"})
        u = s.snapshot()["units"]["ARTABAN"]
        self.assertTrue(u["changed"])
        self.assertEqual(u["vote"], "OPPOSE")

    def test_ireul_alert_recorded(self):
        s = LiveState()
        s.update({"type": "ireul_alert", "categories": ["vote_directive"], "summary": "x"})
        self.assertEqual(s.snapshot()["ireul"]["categories"], ["vote_directive"])

    def test_finished_flag(self):
        s = LiveState()
        s.update({"type": "run_finished", "decision": "SUPPORT"})
        self.assertTrue(s.snapshot()["finished"])


class TestLiveServer(unittest.TestCase):
    def test_board_and_state_endpoints(self):
        state = LiveState()
        server, port = start_server(state, LIVE_BOARD_HTML, port=0)
        try:
            base = f"http://127.0.0.1:{port}"
            html = urllib.request.urlopen(base + "/").read().decode()
            self.assertIn("NERV BRIDGE", html)
            self.assertIn("/state.json", html)  # the board actually polls
            snap = json.loads(urllib.request.urlopen(base + "/state.json").read())
            self.assertIn("phase", snap)
        finally:
            server.shutdown()

    def test_full_deliberation_streams_to_state(self):
        state = LiveState()
        server, port = start_server(state, LIVE_BOARD_HTML, port=0)
        try:
            MagiEngine(mock=True, event_sink=state.update).deliberate("Should MAGI preserve minority reports?")
            snap = json.loads(
                urllib.request.urlopen(f"http://127.0.0.1:{port}/state.json").read()
            )
            self.assertTrue(snap["finished"])
            self.assertIsNotNone(snap["decision"])
            self.assertEqual(len(snap["units"]), 4)
        finally:
            server.shutdown()


class TestEngineSeamIsAdditive(unittest.TestCase):
    def test_no_sink_means_no_change(self):
        # A run without an event_sink must behave exactly as before.
        result = MagiEngine(mock=True).deliberate("Should MAGI preserve minority reports?")
        self.assertIn("decision", result)
        self.assertEqual(len(result["reflections"]), 4)

    def test_events_cover_the_whole_run(self):
        events = []
        MagiEngine(mock=True, event_sink=events.append).deliberate("Should MAGI preserve minority reports?")
        types = {e["type"] for e in events}
        for expected in {"run_started", "round_started", "member_resolved",
                         "reflection_resolved", "decision", "run_finished"}:
            self.assertIn(expected, types)


if __name__ == "__main__":
    unittest.main()
