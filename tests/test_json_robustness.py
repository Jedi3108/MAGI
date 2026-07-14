"""Tests for robust parsing of imperfect model JSON."""

import unittest

from magi.chair.dossier import parse_decision_dossier
from magi.council.members import COUNCIL
from magi.council.verdict import parse_verdict
from magi.protocol.examination import (
    CrossExaminationAnswer,
    RoutedQuestion,
    parse_cross_examination_answer,
    parse_satisfaction_evaluation,
)
from magi.protocol.reflection import parse_reflection


class TestJsonRobustness(unittest.TestCase):
    def test_verdict_recovers_fields_from_valid_json(self):
        member = COUNCIL[0]
        raw = """
        {
          "stance_summary": "I SUPPORT the action.",
          "vote_reason_alignment": "I SUPPORT THE TARGET ACTION BECAUSE the reason supports the action.",
          "action_causality": "IF THE TARGET ACTION IS TAKEN, THEN IT HELPS BECAUSE the reason supports the action.",
          "counterfactual_comparison": "TAKING THE TARGET ACTION IS BETTER THAN NOT TAKING IT BECAUSE the reason supports action.",
          "vote": "SUPPORT",
          "confidence": 88,
          "core_reason": "The claim is supported.",
          "main_risk": "The evidence may be incomplete.",
          "question_for": "NO QUESTIONS",
          "question": "NO QUESTIONS",
          "can_change_mind_if": "Contrary evidence appears."
        }
        """

        verdict = parse_verdict(member=member, raw=raw, model="test")

        self.assertEqual(verdict.vote, "SUPPORT")
        self.assertEqual(verdict.confidence, 88)
        self.assertEqual(verdict.core_reason, "The claim is supported.")

    def test_satisfaction_parser_does_not_display_raw_broken_json(self):
        answer = CrossExaminationAnswer(
            asker_name="CASPER",
            target_name="MELCHIOR",
            question="Why?",
            answer="Because.",
            model="test",
        )

        raw = """
        {
          "satisfaction": "PARTIALLY SATISFIED",
          "reason": "The answer helps but remains incomplete.",
          "confidence_delta": -20
        """

        evaluation = parse_satisfaction_evaluation(
            answer=answer,
            raw=raw,
            model="test",
        )

        self.assertEqual(evaluation.satisfaction, "PARTIALLY SATISFIED")
        self.assertEqual(
            evaluation.reason,
            "The answer helps but remains incomplete.",
        )
        self.assertEqual(evaluation.confidence_delta, -20)
        self.assertFalse(evaluation.reason.strip().startswith("{"))

    def test_reflection_parser_recovers_malformed_json_fields(self):
        member = COUNCIL[2]
        verdict = parse_verdict(
            member=member,
            raw="""
            {
              "stance_summary": "I SUPPORT the action.",
              "vote_reason_alignment": "I SUPPORT THE TARGET ACTION BECAUSE the reason supports the action.",
              "action_causality": "IF THE TARGET ACTION IS TAKEN, THEN IT HELPS BECAUSE the reason supports the action.",
              "counterfactual_comparison": "TAKING THE TARGET ACTION IS BETTER THAN NOT TAKING IT BECAUSE the reason supports action.",
              "vote": "SUPPORT",
              "confidence": 80,
              "core_reason": "Autonomy matters.",
              "main_risk": "Implementation may be unclear.",
              "question_for": "NO QUESTIONS",
              "question": "NO QUESTIONS",
              "can_change_mind_if": "Risks dominate."
            }
            """,
            model="test",
        )

        raw = """
        {
          "learned": "Implementation details matter.",
          "vote_after_reflection": "OPPOSE",
          "confidence_after_reflection": 70,
          "reason": "The debate revealed unresolved risks."
        """

        reflection = parse_reflection(
            member=member,
            verdict=verdict,
            raw=raw,
            model="test",
        )

        self.assertEqual(reflection.vote_after, "OPPOSE")
        self.assertEqual(reflection.confidence_after, 70)
        self.assertEqual(reflection.learned, "Implementation details matter.")
        self.assertFalse(reflection.reason.strip().startswith("{"))

    def test_answer_parser_uses_safe_fallback(self):
        question = RoutedQuestion(
            asker_name="MELCHIOR",
            target_name="BALTHASAR",
            question="Clarify the risk.",
        )

        answer = parse_cross_examination_answer(
            question=question,
            raw="{ broken json",
            model="test",
        )

        self.assertEqual(answer.answer, "No valid answer provided.")

    def test_dossier_parser_uses_safe_fallbacks(self):
        dossier = parse_decision_dossier(
            raw="{ broken json",
            model="test",
            fallback_decision="OPPOSE",
            fallback_split="1 support / 3 oppose",
        )

        self.assertEqual(dossier.decision, "OPPOSE")
        self.assertEqual(dossier.vote_split, "1 support / 3 oppose")
        self.assertEqual(
            dossier.majority_reasoning,
            "No valid majority reasoning provided.",
        )


if __name__ == "__main__":
    unittest.main()


class TestQuestionSafety(unittest.TestCase):
    def test_member_cannot_ask_itself(self):
        member = COUNCIL[1]

        raw = """
        {
          "stance_summary": "I OPPOSE the action.",
          "vote_reason_alignment": "I OPPOSE THE TARGET ACTION BECAUSE the reason opposes the action.",
          "action_causality": "IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE the reason opposes the action.",
          "counterfactual_comparison": "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE the reason opposes action.",
          "vote": "OPPOSE",
          "confidence": 70,
          "core_reason": "Risk remains high.",
          "main_risk": "Self-questioning would waste a protocol slot.",
          "question_for": "BALTHASAR",
          "question": "BALTHASAR, why do you think this?",
          "can_change_mind_if": "Better protocol validation exists."
        }
        """

        verdict = parse_verdict(member=member, raw=raw, model="test")

        self.assertEqual(verdict.question_for, "NO QUESTIONS")
        self.assertEqual(verdict.question, "NO QUESTIONS")
