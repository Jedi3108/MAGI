"""MAGI council execution engine."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from magi.council.members import COUNCIL, CouncilMember
from magi.council.verdict import Verdict, parse_verdict
from magi.models.mock import mock_verdict
from magi.models.ollama import chat, installed_models


DEFAULT_MODEL = "llama3.2"


JUDGE_INSTRUCTION = """
Evaluate the proposition strictly through your council identity.

Return ONLY a JSON object. No prose. No markdown.

Required schema:
{{
  "vote": "AFFIRMATIVE" | "NEGATIVE",
  "confidence": 0-100,
  "core_reason": "one or two sentences",
  "main_risk": "one sentence",
  "question_for": "MELCHIOR" | "BALTHASAR" | "CASPER" | "ARTABAN" | "NO QUESTIONS",
  "question": "one important question, or NO QUESTIONS",
  "can_change_mind_if": "what evidence or argument could change your vote"
}}

Proposition:
{proposition}
"""


class MagiEngine:
    """Runs the MAGI council."""

    def __init__(
        self,
        model: str | None = None,
        mock: bool = False,
        same: bool = False,
        default_model: str = DEFAULT_MODEL,
    ) -> None:
        self.mock = mock
        self.default_model = default_model
        self.models = self._resolve_models(model=model, same=same)

    def _resolve_models(self, model: str | None, same: bool) -> dict[str, str]:
        if model:
            return {member.name: model for member in COUNCIL}

        if same or self.mock:
            return {member.name: self.default_model for member in COUNCIL}

        available = installed_models()
        resolved: dict[str, str] = {}

        for member in COUNCIL:
            if member.preferred_model in available:
                resolved[member.name] = member.preferred_model
            else:
                resolved[member.name] = self.default_model

        return resolved

    def _ask_member(self, member: CouncilMember, proposition: str) -> Verdict:
        model = self.models[member.name]
        user_prompt = JUDGE_INSTRUCTION.format(proposition=proposition)

        if self.mock:
            raw = mock_verdict(member.name, user_prompt)
            model = "mock"
        else:
            raw = chat(model=model, system=member.persona, user=user_prompt)

        return parse_verdict(member=member, raw=raw, model=model)

    def independent_analysis(self, proposition: str) -> list[Verdict]:
        """Run independent council analysis."""
        with ThreadPoolExecutor(max_workers=len(COUNCIL)) as pool:
            return list(pool.map(lambda member: self._ask_member(member, proposition), COUNCIL))

    def deliberate(self, proposition: str) -> dict:
        """Run the current council protocol."""
        verdicts = self.independent_analysis(proposition)
        decision = decide(verdicts)

        return {
            "proposition": proposition,
            "verdicts": verdicts,
            "decision": decision,
        }


def decide(verdicts: list[Verdict]) -> dict:
    """Decide by simple majority; ties are reported as no consensus."""
    affirmative = [verdict for verdict in verdicts if verdict.approves]
    negative = [verdict for verdict in verdicts if not verdict.approves]

    if len(affirmative) > len(negative):
        decision = "AFFIRMATIVE"
    elif len(negative) > len(affirmative):
        decision = "NEGATIVE"
    else:
        decision = "NO CONSENSUS"

    return {
        "decision": decision,
        "affirmative": len(affirmative),
        "negative": len(negative),
    }
