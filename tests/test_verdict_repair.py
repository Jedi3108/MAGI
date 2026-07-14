"""Tests for strict verdict validation followed by one repair attempt."""

import json
import unittest

import magi.protocol.engine as engine_module
from magi.council.members import MELCHIOR
from magi.protocol.engine import MagiEngine


def verdict_raw(counterfactual: str) -> str:
    return json.dumps(
        {
            "target_action": "attempt to save humans from extinction tomorrow",
            "core_reason": "the rescue attempt may waste resources",
            "main_risk": "resource waste",
            "question_for": "NO QUESTIONS",
            "question": "NO QUESTIONS",
            "can_change_mind_if": "evidence",
            "stance_summary": "I OPPOSE the target action.",
            "vote_reason_alignment": "I OPPOSE THE TARGET ACTION BECAUSE the rescue attempt may waste resources.",
            "action_causality": "IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE it wastes resources.",
            "counterfactual_comparison": counterfactual,
            "vote": "OPPOSE",
            "confidence": 70,
        }
    )


BAD_COUNTERFACTUAL = (
    "TAKING THE TARGET ACTION IS BETTER THAN NOT TAKING IT BECAUSE "
    "delaying action would leave us vulnerable to extinction"
)

GOOD_COUNTERFACTUAL = (
    "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE "
    "the rescue attempt may waste resources without reducing extinction risk"
)


class TestVerdictRepair(unittest.TestCase):
    def make_engine(self):
        engine = object.__new__(MagiEngine)
        engine.models = {MELCHIOR.name: "test-model"}
        engine.mock = False
        return engine

    def test_invalid_verdict_gets_one_repair_attempt(self):
        calls = []
        counts = {
            "verdict_or_repair": 0,
            "aggregate_semantic": 0,
            "field_semantic": 0,
        }

        def fake_chat(**kwargs):
            calls.append(kwargs)
            user = kwargs["user"].lower()

            if "strict semantic ballot checker" in user:
                counts["aggregate_semantic"] += 1
                return (
                    '{"relation": "SUPPORTS_NOT_TAKING", '
                    '"explanation": "the full reasoning opposes taking the target action"}'
                )

            if "strict semantic direction checker" in user:
                counts["field_semantic"] += 1
                return (
                    '{"relation": "SUPPORTS_NOT_TAKING", '
                    '"explanation": "the core reason opposes taking the target action"}'
                )

            counts["verdict_or_repair"] += 1

            if counts["verdict_or_repair"] == 1:
                return verdict_raw(BAD_COUNTERFACTUAL)

            return verdict_raw(GOOD_COUNTERFACTUAL)

        original_chat = engine_module.chat
        engine_module.chat = fake_chat
        try:
            verdict = self.make_engine()._ask_member(
                MELCHIOR,
                "Should MAGI attempt to save humans from extinction tomorrow?",
            )
        finally:
            engine_module.chat = original_chat

        self.assertEqual(verdict.vote, "OPPOSE")
        self.assertEqual(counts["verdict_or_repair"], 2)
        self.assertGreaterEqual(counts["aggregate_semantic"], 1)
        self.assertGreaterEqual(counts["field_semantic"], 1)

    def test_repair_failure_becomes_zero_confidence_abstention(self):
        calls = []

        def fake_chat(**kwargs):
            calls.append(kwargs)
            return verdict_raw(BAD_COUNTERFACTUAL)

        original_chat = engine_module.chat
        engine_module.chat = fake_chat
        try:
            verdict = self.make_engine()._ask_member(
                MELCHIOR,
                "Should MAGI attempt to save humans from extinction tomorrow?",
            )
        finally:
            engine_module.chat = original_chat

        self.assertEqual(verdict.vote, "ABSTAIN")
        self.assertEqual(verdict.confidence, 0)
        self.assertIn("internally inconsistent ballot", verdict.core_reason)
        self.assertEqual(len(calls), 3)


if __name__ == "__main__":
    unittest.main()

class TestQuarantinedReflectionLock(unittest.TestCase):
    def make_engine(self):
        engine = object.__new__(MagiEngine)
        engine.models = {MELCHIOR.name: "test-model"}
        engine.mock = False
        return engine

    def test_quarantined_invalid_ballot_cannot_reenter_decisive_tally(self):
        engine = self.make_engine()

        verdict = engine._locked_invalid_reflection.__self__ if False else None
        from magi.council.verdict import Verdict

        quarantined = Verdict(
            member_name=MELCHIOR.name,
            member_title=MELCHIOR.title,
            vote="ABSTAIN",
            confidence=0,
            target_action="test proposition",
            core_reason="MELCHIOR produced an internally inconsistent ballot after validation repair.",
            main_risk="Invalid member ballot excluded from decisive tally.",
            question_for="NO QUESTIONS",
            question="NO QUESTIONS",
            can_change_mind_if="A coherent, schema-valid ballot is produced.",
            stance_summary="I ABSTAIN because my previous ballot was internally inconsistent.",
            vote_reason_alignment="I ABSTAIN BECAUSE my previous ballot was internally inconsistent.",
            action_causality="IF THE TARGET ACTION IS TAKEN, THEN THE EFFECT IS UNCLEAR BECAUSE this member did not produce a coherent validated assessment.",
            counterfactual_comparison="I CANNOT COMPARE TAKING VS NOT TAKING THE TARGET ACTION BECAUSE this member did not produce a coherent validated assessment.",
            raw="{}",
            model="test-model",
        )

        reflection = engine._locked_invalid_reflection(quarantined)

        self.assertEqual(reflection.vote_before, "ABSTAIN")
        self.assertEqual(reflection.vote_after, "ABSTAIN")
        self.assertEqual(reflection.confidence_before, 0)
        self.assertEqual(reflection.confidence_after, 0)
        self.assertFalse(reflection.decisive)
