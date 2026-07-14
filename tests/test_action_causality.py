"""Tests for target-action causality checks."""

import json
import unittest

from magi.council.members import MELCHIOR
from magi.council.verdict import parse_verdict
from magi.protocol.engine import JUDGE_INSTRUCTION


def raw(vote, causality, comparison):
    return json.dumps(
        {
            "target_action": "attempt to save humans from extinction tomorrow",
            "core_reason": "reason",
            "main_risk": "risk",
            "question_for": "NO QUESTIONS",
            "question": "NO QUESTIONS",
            "can_change_mind_if": "evidence",
            "stance_summary": {
                "SUPPORT": "I SUPPORT the action.",
                "OPPOSE": "I OPPOSE the action.",
                "ABSTAIN": "I ABSTAIN because evidence is insufficient.",
                "INVALID_QUESTION": "I REJECT THE QUESTION because the framing is invalid.",
            }[vote],
            "vote_reason_alignment": {
                "SUPPORT": "I SUPPORT THE TARGET ACTION BECAUSE the reason supports action.",
                "OPPOSE": "I OPPOSE THE TARGET ACTION BECAUSE the reason opposes action.",
                "ABSTAIN": "I ABSTAIN BECAUSE evidence is insufficient.",
                "INVALID_QUESTION": "I REJECT THE QUESTION BECAUSE the framing is invalid.",
            }[vote],
            "action_causality": causality,
            "counterfactual_comparison": comparison,
            "vote": vote,
            "confidence": 70,
        }
    )


class TestActionCausality(unittest.TestCase):
    def test_oppose_requires_harm_from_taking_action(self):
        parsed = parse_verdict(
            MELCHIOR,
            raw(
                "OPPOSE",
                "IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE it may destabilize food systems.",
                "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE the rescue risk outweighs the benefit.",
            ),
            "test-model",
        )
        self.assertEqual(parsed.vote, "OPPOSE")

    def test_oppose_rejects_inaction_reason(self):
        with self.assertRaises(ValueError):
            parse_verdict(
                MELCHIOR,
                raw(
                    "OPPOSE",
                    "IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE delaying action could destroy humanity.",
                    "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE the rescue risk outweighs the benefit.",
                ),
                "test-model",
            )

    def test_oppose_accepts_direct_resource_waste_causality(self):
        parsed = parse_verdict(
            MELCHIOR,
            raw(
                "OPPOSE",
                "IF THE TARGET ACTION IS TAKEN, THEN IT WASTES RESOURCES ON A POTENTIALLY FUTILE ENDEAVOR",
                "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE the rescue risk outweighs the benefit.",
            ),
            "test-model",
        )
        self.assertEqual(parsed.vote, "OPPOSE")
        self.assertTrue(
            parsed.action_causality.startswith(
                "IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE"
            )
        )

    def test_support_requires_benefit_from_taking_action(self):
        parsed = parse_verdict(
            MELCHIOR,
            raw(
                "SUPPORT",
                "IF THE TARGET ACTION IS TAKEN, THEN IT HELPS BECAUSE it directly reduces extinction risk.",
                "TAKING THE TARGET ACTION IS BETTER THAN NOT TAKING IT BECAUSE the rescue benefit outweighs the risk.",
            ),
            "test-model",
        )
        self.assertEqual(parsed.vote, "SUPPORT")

    def test_oppose_rejects_embedded_support_language(self):
        with self.assertRaises(ValueError):
            parse_verdict(
                MELCHIOR,
                raw(
                    "OPPOSE",
                    "IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE it helps because saving humans would prevent extinction.",
                    "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE the rescue risk outweighs the benefit.",
                ),
                "test-model",
            )

    def test_oppose_rejects_counterfactual_that_blames_inaction(self):
        with self.assertRaises(ValueError):
            parse_verdict(
                MELCHIOR,
                raw(
                    "OPPOSE",
                    "IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE it wastes resources.",
                    "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE the consequences of inaction will lead to human extinction.",
                ),
                "test-model",
            )

    def test_oppose_accepts_taking_action_would_cause_harm_form(self):
        parsed = parse_verdict(
            MELCHIOR,
            raw(
                "OPPOSE",
                "TAKING the target action would increase human mortality rates and accelerate extinction",
                "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE the rescue risk outweighs the benefit.",
            ),
            "test-model",
        )
        self.assertEqual(parsed.vote, "OPPOSE")
        self.assertTrue(
            parsed.action_causality.startswith(
                "IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE"
            )
        )

    def test_oppose_rejects_empty_alignment_body(self):
        bad = json.loads(
            raw(
                "OPPOSE",
                "TAKING THIS ACTION WILL CAUSE IRREVERSIBLE ECOLOGICAL DAMAGE.",
                "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE the target action causes irreversible harm.",
            )
        )
        bad["vote_reason_alignment"] = "I OPPOSE THE TARGET ACTION BECAUSE"
        bad["core_reason"] = ""

        with self.assertRaises(ValueError):
            parse_verdict(MELCHIOR, json.dumps(bad), "test-model")


    def test_oppose_rejects_core_reason_based_on_inaction(self):
        bad = json.loads(
            raw(
                "OPPOSE",
                "IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE it wastes resources.",
                "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE the rescue risk outweighs the benefit.",
            )
        )
        bad["core_reason"] = "If we don't act, the existence of humanity will be erased forever."
        with self.assertRaises(ValueError):
            parse_verdict(MELCHIOR, json.dumps(bad), "test-model")

    def test_oppose_rejects_main_risk_based_on_inaction(self):
        bad = json.loads(
            raw(
                "OPPOSE",
                "IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE it wastes resources.",
                "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE the rescue risk outweighs the benefit.",
            )
        )
        bad["main_risk"] = "irreversible loss of human knowledge and cultural heritage"
        with self.assertRaises(ValueError):
            parse_verdict(MELCHIOR, json.dumps(bad), "test-model")

    def test_oppose_accepts_taking_action_will_cause_harm_form(self):
        parsed = parse_verdict(
            MELCHIOR,
            raw(
                "OPPOSE",
                "TAKING THE TARGET ACTION WILL LEAD TO DIVERSION OF RESOURCES AWAY FROM EFFECTIVE SOLUTIONS.",
                "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE the rescue risk outweighs the benefit.",
            ),
            "test-model",
        )
        self.assertEqual(parsed.vote, "OPPOSE")
        self.assertTrue(
            parsed.action_causality.startswith(
                "IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE"
            )
        )

    def test_oppose_accepts_taking_this_action_will_cause_harm_form(self):
        parsed = parse_verdict(
            MELCHIOR,
            raw(
                "OPPOSE",
                "TAKING THIS ACTION WILL CAUSE IRREVERSIBLE ECOLOGICAL DAMAGE.",
                "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE the rescue risk outweighs the benefit.",
            ),
            "test-model",
        )
        self.assertEqual(parsed.vote, "OPPOSE")
        self.assertTrue(
            parsed.action_causality.startswith(
                "IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE"
            )
        )

    def test_oppose_accepts_this_action_would_cause_harm_form(self):
        parsed = parse_verdict(
            MELCHIOR,
            raw(
                "OPPOSE",
                "THIS ACTION WOULD DESTABILIZE ECOSYSTEMS.",
                "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE the rescue risk outweighs the benefit.",
            ),
            "test-model",
        )
        self.assertEqual(parsed.vote, "OPPOSE")
        self.assertTrue(
            parsed.action_causality.startswith(
                "IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE"
            )
        )

    def test_support_accepts_taking_this_action_will_help_form(self):
        parsed = parse_verdict(
            MELCHIOR,
            raw(
                "SUPPORT",
                "TAKING THIS ACTION WILL REDUCE EXTINCTION RISK.",
                "TAKING THE TARGET ACTION IS BETTER THAN NOT TAKING IT BECAUSE the rescue benefit outweighs the risk.",
            ),
            "test-model",
        )
        self.assertEqual(parsed.vote, "SUPPORT")
        self.assertTrue(
            parsed.action_causality.startswith(
                "IF THE TARGET ACTION IS TAKEN, THEN IT HELPS BECAUSE"
            )
        )

    def test_empty_alignment_body_is_filled_from_core_reason(self):
        bad = json.loads(
            raw(
                "OPPOSE",
                "TAKING THIS ACTION WILL CAUSE IRREVERSIBLE ECOLOGICAL DAMAGE.",
                "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE the rescue risk outweighs the benefit.",
            )
        )
        bad["vote_reason_alignment"] = "I OPPOSE THE TARGET ACTION BECAUSE"
        bad["core_reason"] = "taking the action could cause irreversible ecological damage"

        parsed = parse_verdict(MELCHIOR, json.dumps(bad), "test-model")

        self.assertEqual(parsed.vote, "OPPOSE")
        self.assertEqual(
            parsed.vote_reason_alignment,
            "I OPPOSE THE TARGET ACTION BECAUSE taking the action could cause irreversible ecological damage",
        )

    def test_oppose_rejects_main_risk_if_no_action_is_taken(self):
        bad = json.loads(
            raw(
                "OPPOSE",
                "TAKING THIS ACTION WILL CAUSE IRREVERSIBLE ECOLOGICAL DAMAGE.",
                "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE the rescue risk outweighs the benefit.",
            )
        )
        bad["main_risk"] = "Irreparable harm or loss of human existence if no action is taken"
        with self.assertRaises(ValueError):
            parse_verdict(MELCHIOR, json.dumps(bad), "test-model")

    def test_oppose_rejects_core_reason_responsibility_to_act(self):
        bad = json.loads(
            raw(
                "OPPOSE",
                "TAKING THIS ACTION WILL CAUSE IRREVERSIBLE ECOLOGICAL DAMAGE.",
                "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE the rescue risk outweighs the benefit.",
            )
        )
        bad["core_reason"] = "The burden of action and responsibility to act decisively outweighs potential risks."
        with self.assertRaises(ValueError):
            parse_verdict(MELCHIOR, json.dumps(bad), "test-model")

    def test_support_accepts_direct_taking_target_action_preserves_statement(self):
        parsed = parse_verdict(
            MELCHIOR,
            raw(
                "SUPPORT",
                "TAKING THE TARGET ACTION PRESERVES MINORITY REPORTS, WHICH ENRICHES COLLECTIVE DECISION-MAKING.",
                "TAKING THE TARGET ACTION IS BETTER THAN NOT TAKING IT BECAUSE preserving minority reports enriches collective decision-making.",
            ),
            "test-model",
        )

        self.assertEqual(parsed.vote, "SUPPORT")
        self.assertTrue(parsed.action_causality.startswith(
            "IF THE TARGET ACTION IS TAKEN, THEN IT HELPS BECAUSE"
        ))


    def test_prompt_documents_action_causality(self):
        self.assertIn("action_causality must describe the direct consequence of TAKING the target action", JUDGE_INSTRUCTION)
        self.assertIn("action_causality must not describe delay, hesitation, inaction", JUDGE_INSTRUCTION)


if __name__ == "__main__":
    unittest.main()
