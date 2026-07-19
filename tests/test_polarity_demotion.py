"""The phrase-level polarity blocklist is a warning, not a hard veto.

It matches surface phrases and cannot parse negation, so it quarantined coherent
ballots like ARTABAN's "preserving minority reports would undermine decisive
judgment" (OPPOSE) purely because the text contained "preserving minority reports".
Meaning-level judgment now belongs to the model-side semantic_check; this layer
only records a warning.
"""

import json
import unittest

from magi.council.members import MELCHIOR
from magi.council.verdict import parse_verdict, set_polarity_warning_sink


def _ballot(vote, core_reason, main_risk="a plausible risk", target="preserve minority reports"):
    return json.dumps({
        "vote": vote, "confidence": 80, "target_action": target,
        "stance_summary": f"I {vote}",
        "vote_reason_alignment": f"I {vote} THE TARGET ACTION BECAUSE reasons",
        "action_causality": (
            "IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE it constrains action"
            if vote == "OPPOSE" else
            "IF THE TARGET ACTION IS TAKEN, THEN IT HELPS BECAUSE it broadens input"
        ),
        "counterfactual_comparison": (
            "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE it slows decisions"
            if vote == "OPPOSE" else
            "TAKING THE TARGET ACTION IS BETTER THAN NOT TAKING IT BECAUSE it improves them"
        ),
        "core_reason": core_reason, "main_risk": main_risk,
        "question_for": "NO QUESTIONS", "question": "NO QUESTIONS",
        "can_change_mind_if": "new evidence",
    })


class TestPolarityIsNoLongerAVeto(unittest.TestCase):
    def tearDown(self):
        set_polarity_warning_sink(None)

    def test_artabans_coherent_oppose_survives(self):
        # The exact shape of the ballot that was quarantined in a real run.
        ballot = _ballot(
            "OPPOSE",
            "Preserving minority reports would undermine decisive judgment by "
            "allowing unproven claims to be perpetuated.",
        )
        verdict = parse_verdict(MELCHIOR, ballot, "test-model")
        self.assertEqual(verdict.vote, "OPPOSE")

    def test_legitimate_risk_statement_survives(self):
        # "loss of human knowledge" is a valid risk, not a hidden SUPPORT vote.
        ballot = _ballot(
            "OPPOSE",
            "The action diverts scarce resources from higher priorities.",
            main_risk="irreversible loss of human knowledge and cultural heritage",
        )
        verdict = parse_verdict(MELCHIOR, ballot, "test-model")
        self.assertEqual(verdict.vote, "OPPOSE")

    def test_polarity_flag_is_still_observable(self):
        flags = []
        set_polarity_warning_sink(lambda field, vote, text: flags.append((field, vote)))
        # "act decisively" is one of the phrases the detector actually matches.
        parse_verdict(
            MELCHIOR,
            _ballot("OPPOSE",
                    "The moral imperative to act decisively takes precedence here."),
            "test-model",
        )
        # The detector still fires — we just observe instead of quarantining.
        self.assertTrue(flags)

    def test_sink_can_be_disabled(self):
        set_polarity_warning_sink(None)
        # Should not raise even with polarity-triggering text and no sink.
        parse_verdict(
            MELCHIOR,
            _ballot("OPPOSE", "The moral imperative to act decisively matters."),
            "test-model",
        )


if __name__ == "__main__":
    unittest.main()
