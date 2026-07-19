"""The inaction-language veto is scoped to the fields where it makes sense.

main_risk describes a failure mode, which is inherently about what goes wrong if
the action is NOT taken. Running the inaction veto there is a category error that
killed correct risk statements (it was a joint top ballot-killer after the polarity
demotion). The veto stays on core_reason; genuine reason-vote inversions are caught
by the structured causal fields and the model-side semantic check.
"""

import json
import unittest

from magi.council.members import MELCHIOR
from magi.council.verdict import parse_verdict


def _ballot(core_reason="it constrains decisive action", main_risk="a plausible downside"):
    return json.dumps({
        "vote": "OPPOSE", "confidence": 80, "target_action": "preserve minority reports",
        "stance_summary": "I OPPOSE",
        "vote_reason_alignment": "I OPPOSE THE TARGET ACTION BECAUSE it slows decisions",
        "action_causality": "IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE it constrains action",
        "counterfactual_comparison": "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE it slows decisions",
        "core_reason": core_reason, "main_risk": main_risk,
        "question_for": "NO QUESTIONS", "question": "NO QUESTIONS", "can_change_mind_if": "evidence",
    })


class TestInactionScope(unittest.TestCase):
    def test_main_risk_may_reference_inaction(self):
        # "if we don't preserve it" in a RISK field is correct, not an inversion.
        v = parse_verdict(
            MELCHIOR,
            _ballot(main_risk="dissenting insight is lost if we do not preserve minority reports"),
            "test-model",
        )
        self.assertEqual(v.vote, "OPPOSE")
        self.assertIn("lost if we do not", v.main_risk)

    def test_main_risk_with_consequences_of_inaction_survives(self):
        v = parse_verdict(
            MELCHIOR,
            _ballot(main_risk="the consequences of inaction include overlooked risks"),
            "test-model",
        )
        self.assertEqual(v.vote, "OPPOSE")

    def test_core_reason_still_rejects_explicit_inaction_justification(self):
        # An OPPOSE justified by "inaction leads to..." is a genuine inversion.
        with self.assertRaises(ValueError):
            parse_verdict(
                MELCHIOR,
                _ballot(core_reason="the consequences of inaction would be catastrophic"),
                "test-model",
            )


if __name__ == "__main__":
    unittest.main()
