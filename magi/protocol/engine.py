"""MAGI council execution engine."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from magi.chair.dossier import DecisionDossier, parse_decision_dossier
from magi.chair.record import build_structured_chair_record
from magi.council.members import CHAIR_SAMPLING, COUNCIL, CouncilMember
from magi.council.verdict import Verdict, parse_verdict
from magi.models.mock import (
    mock_answer,
    mock_chair_dossier,
    mock_evaluation,
    mock_reflection,
    mock_verdict,
)
from magi.models.ollama import (
    OllamaModelNotFoundError,
    chat,
    installed_models,
    resolve_model_name,
)
from magi.protocol.examination import (
    CrossExaminationAnswer,
    RoutedQuestion,
    SatisfactionEvaluation,
    collect_questions,
    parse_cross_examination_answer,
    parse_satisfaction_evaluation,
)
from magi.protocol.reflection import Reflection, parse_reflection


DEFAULT_MODEL = "llama3.2"


JUDGE_INSTRUCTION = """
You are taking part in Round 1 of the MAGI deliberation protocol: Independent Analysis.

You are ONE facet of the council, and only one. Judge this proposition strictly
through your own charge, as defined by your identity in the system prompt.

Do not reason on behalf of the other members.
Do not try to be balanced. Do not average competing concerns.
Balance is the council's job, not yours. Your job is to represent your facet without compromise.

Do not imitate the other council members.
Do not give a generic assistant answer.
Do not retreat to the safe, agreeable, or middle-of-the-road position.
Do not force consensus.

If your facet pulls against the obvious answer, follow your facet and name the conflict openly.
Disagreement is allowed.
A minority position is valuable if it exposes a real concern your facet sees and others would miss.

Your core_reason must be the judgment your facet forces on you,
not a summary of what a reasonable person would conclude.

Confidence calibration:
- 50 means genuinely uncertain.
- 60 means weak lean.
- 70 means clear but revisable position.
- 80 means strong position with some uncertainty.
- 90+ should be rare and requires unusually strong justification.

Return ONLY one valid JSON object.
No prose, no markdown, no comments, no trailing text.
All string values must be plain text.

Required schema:
{{
  "vote": "AFFIRMATIVE" | "NEGATIVE",
  "confidence": 0-100,
  "core_reason": "one concrete reason, written in your council voice",
  "main_risk": "one concrete failure mode or danger",
  "question_for": "MELCHIOR" | "BALTHASAR" | "CASPER" | "ARTABAN" | "NO QUESTIONS",
  "question": "one sharp question to another member, or NO QUESTIONS",
  "can_change_mind_if": "specific evidence, condition, or argument that could change your vote"
}}

Proposition:
{proposition}
"""


ANSWER_INSTRUCTION = """
You are in Round 2 of the MAGI deliberation protocol: Cross-Examination.

The proposition is:
{proposition}

Round 1 council context:
{council_context}

A question was addressed to you by {asker_name}:

{question}

Answer directly through your council identity.

Rules:
- Answer the actual question, not a different one.
- Give one clear answer and one supporting reason.
- If the asker raised a valid concern, acknowledge it.
- Avoid slogans, filler, and generic safety language.
- Do not change your role.

Return ONLY one valid JSON object.
No prose, no markdown, no comments, no trailing text.
All string values must be plain text.

Required schema:
{{
  "answer": "direct answer, two to four sentences"
}}
"""


EVALUATION_INSTRUCTION = """
You are in Round 3 of the MAGI deliberation protocol: Satisfaction Evaluation.

The proposition is:
{proposition}

You asked {target_name} this question:
{question}

{target_name} answered:
{answer}

Evaluate whether the answer satisfied your concern.

Rules:
- Judge the answer from your own council identity.
- Do not be polite by default.
- Do not be hostile by default.
- Explain what was resolved and what remains unresolved.
- Confidence deltas should usually be modest unless the answer strongly changes your position.

Return ONLY one valid JSON object.
No prose, no markdown, no comments, no trailing text.
All string values must be plain text.

Required schema:
{{
  "satisfaction": "SATISFIED" | "PARTIALLY SATISFIED" | "NOT SATISFIED",
  "reason": "one or two sentences explaining your evaluation",
  "confidence_delta": -100 to 100
}}
"""


REFLECTION_INSTRUCTION = """
You are in Round 4 of the MAGI deliberation protocol: Reflection.

The proposition is:
{proposition}

Your original position:
Vote: {vote_before}
Confidence: {confidence_before}
Reason: {core_reason}
Risk: {main_risk}

In Round 1 you committed, in your own words, to the ONE condition under which you would change your vote:
"{change_condition}"

Council deliberation context:
{deliberation_context}

Reflect on the exchange.

Refutation gate — apply this BEFORE deciding your vote:
- Identify the single strongest argument raised against your core reason.
- Ask honestly: did it DEFEAT your core reason, or did it merely offer a reasonable-sounding alternative?
- A compromise, a hybrid proposal, or a middle-ground solution is NOT a defeater.
- Another member's confidence, or the discussion converging toward agreement, is NOT a defeater. Social agreement is not evidence.
- You may change your vote ONLY if the specific condition you named above was actually met by the debate.
- If that condition was not met, you MUST preserve your vote. You may lower your confidence to reflect new sympathy or doubt, but you may not flip.

Rules:
- State what you genuinely learned, if anything.
- Preserve your vote if the exchange did not defeat your core reason.
- Change your vote only if the debate exposed a stronger reason that meets your own stated condition.
- Do not abandon your facet because the rest of the council disagreed with you. A lone position that was not refuted must be held.
- Adjust confidence realistically.
- Your learned statement, final vote, confidence, and reason must not contradict each other.
- If your reasoning now supports the opposite vote, change the vote or explain why you still reject it.
- Do not increase confidence when your own reason emphasizes unresolved uncertainty.
- Avoid repeating your original answer word-for-word.
- Stay within your council identity.

Return ONLY one valid JSON object.
No prose, no markdown, no comments, no trailing text.
All string values must be plain text.

Required schema:
{{
  "learned": "one or two sentences about what changed in your understanding",
  "vote_after_reflection": "AFFIRMATIVE" | "NEGATIVE",
  "confidence_after_reflection": 0-100,
  "reason": "one or two sentences explaining why your vote/confidence changed or stayed the same"
}}
"""


CHAIR_INSTRUCTION = """
You are the non-voting Chair of the MAGI council.

You do not vote.
You do not add a new opinion.
You do not invent arguments that were not present.
Your task is to turn the actual deliberation into a clear decision dossier.

The proposition is:
{proposition}

Final decision:
{decision}

Vote split:
{vote_split}

Authoritative final reflected vote record:
{final_vote_record}

Full council transcript:
{council_record}

The authoritative final reflected vote record overrides the transcript if they appear to conflict.
The final reflected votes are authoritative.
Use each member's final reflected vote and final reflected confidence when summarizing positions.
Do not treat Round 1 votes or Round 1 confidence values as final positions.
Do not attribute AFFIRMATIVE reasoning to a member whose final reflected vote is NEGATIVE, or NEGATIVE reasoning to a member whose final reflected vote is AFFIRMATIVE.

Dossier rules:
- Base vote attribution on the authoritative final reflected vote record, not on inference from prose.
- If the decision is AFFIRMATIVE or NEGATIVE, summarize the majority reasoning faithfully.
- If the decision is NO CONSENSUS, state that no majority exists and summarize the competing positions instead.
- Preserve minority reasoning if any member dissented.
- If there is no minority after reflection, say so clearly.
- Identify unresolved questions without pretending they are solved.
- Never leave dossier fields empty. If none exist, write a clear sentence such as: None identified in the council record.
- Recommended next action must be concrete and operational.
- Write in clean professional language.

Return ONLY one valid JSON object.
No prose, no markdown, no comments, no trailing text.
All string values must be plain text.

Required schema:
{{
  "decision": "AFFIRMATIVE" | "NEGATIVE" | "NO CONSENSUS",
  "vote_split": "text summary of the final vote split",
  "majority_reasoning": "summary based on final reflected votes only; if NO CONSENSUS: state that no majority exists and summarize the competing final positions",
  "minority_reasoning": "summary based on final reflected votes only; if NO CONSENSUS: summarize the unresolved opposing final positions",
  "key_risks": "main risks identified by the council",
  "outstanding_uncertainties": "what remains unresolved, or: None identified in the council record",
  "required_conditions": "conditions under which the decision should be accepted, or: None identified in the council record",
  "recommended_next_action": "one concrete next step"
}}
"""


class MagiEngine:
    """Runs the MAGI council."""

    def __init__(
        self,
        model: str | None = None,
        mock: bool = False,
        same: bool = False,
        progress: Callable[[str], None] | None = None,
        default_model: str = DEFAULT_MODEL,
    ) -> None:
        self.mock = mock
        self.default_model = default_model
        self.progress = progress
        self.model_notes: list[str] = []

        self.models = self._resolve_models(model=model, same=same)
        self.chair_model = "mock" if mock else self._resolve_chair_model(model=model)

    def _progress(self, message: str) -> None:
        """Emit a progress message if a progress callback is configured."""
        if self.progress:
            self.progress(message)

    def _resolve_required_model(self, requested: str, available: list[str]) -> str:
        resolved = resolve_model_name(requested, available)
        if not resolved:
            raise OllamaModelNotFoundError(requested=requested, available=available)
        return resolved

    def _resolve_chair_model(self, model: str | None) -> str:
        if self.mock:
            return "mock"

        available = installed_models()
        requested = model or self.default_model

        resolved = resolve_model_name(requested, available)
        if resolved:
            return resolved

        if available:
            fallback = available[0]
            self.model_notes.append(
                f"Chair fallback: requested {requested!r}, using {fallback!r}."
            )
            return fallback

        raise OllamaModelNotFoundError(requested=requested, available=available)

    def _resolve_models(self, model: str | None, same: bool) -> dict[str, str]:
        if self.mock:
            return {member.name: self.default_model for member in COUNCIL}

        available = installed_models()

        if model:
            resolved = self._resolve_required_model(model, available)
            return {member.name: resolved for member in COUNCIL}

        if same:
            resolved = self._resolve_required_model(self.default_model, available)
            return {member.name: resolved for member in COUNCIL}

        resolved_models: dict[str, str] = {}

        for member in COUNCIL:
            preferred = resolve_model_name(member.preferred_model, available)

            if preferred:
                resolved_models[member.name] = preferred
                continue

            default = resolve_model_name(self.default_model, available)

            if default:
                resolved_models[member.name] = default
                self.model_notes.append(
                    f"{member.name} fallback: preferred {member.preferred_model!r}, "
                    f"using default {default!r}."
                )
                continue

            if available:
                fallback = available[0]
                resolved_models[member.name] = fallback
                self.model_notes.append(
                    f"{member.name} fallback: preferred {member.preferred_model!r} "
                    f"and default {self.default_model!r} unavailable, using {fallback!r}."
                )
                continue

            raise OllamaModelNotFoundError(
                requested=self.default_model,
                available=available,
            )

        return resolved_models

    def _ask_member(self, member: CouncilMember, proposition: str) -> Verdict:
        model = self.models[member.name]
        user_prompt = JUDGE_INSTRUCTION.format(proposition=proposition)

        if self.mock:
            raw = mock_verdict(member.name, user_prompt)
            model = "mock"
        else:
            s = member.sampling
            raw = chat(
                model=model,
                system=member.persona,
                user=user_prompt,
                temperature=s.temperature,
                top_p=s.top_p,
                repeat_penalty=s.repeat_penalty,
                response_format="json",
            )

        return parse_verdict(member=member, raw=raw, model=model)

    def independent_analysis(self, proposition: str) -> list[Verdict]:
        """Run independent council analysis."""
        with ThreadPoolExecutor(max_workers=len(COUNCIL)) as pool:
            return list(pool.map(lambda member: self._ask_member(member, proposition), COUNCIL))

    def _member_by_name(self, name: str) -> CouncilMember:
        for member in COUNCIL:
            if member.name == name:
                return member
        raise ValueError(f"Unknown council member: {name}")

    def _verdict_by_member(self, verdicts: list[Verdict], name: str) -> Verdict:
        for verdict in verdicts:
            if verdict.member_name == name:
                return verdict
        raise ValueError(f"No verdict found for: {name}")

    def _council_context(self, verdicts: list[Verdict]) -> str:
        return "\n".join(
            (
                f"- {verdict.member_name}: {verdict.vote} "
                f"({verdict.confidence}%). "
                f"Reason: {verdict.core_reason} "
                f"Risk: {verdict.main_risk}"
            )
            for verdict in verdicts
        )

    def _deliberation_context(
        self,
        answers: list[CrossExaminationAnswer],
        evaluations: list[SatisfactionEvaluation],
    ) -> str:
        answer_lines = [
            (
                f"- {answer.asker_name} asked {answer.target_name}: "
                f"{answer.question} Answer: {answer.answer}"
            )
            for answer in answers
        ]

        evaluation_lines = [
            (
                f"- {evaluation.asker_name} evaluated {evaluation.target_name}: "
                f"{evaluation.satisfaction}. Reason: {evaluation.reason} "
                f"Confidence delta: {evaluation.confidence_delta:+d}"
            )
            for evaluation in evaluations
        ]

        if not answer_lines and not evaluation_lines:
            return "No cross-examination occurred."

        return "\n".join(answer_lines + evaluation_lines)

    def _council_record(
        self,
        verdicts: list[Verdict],
        answers: list[CrossExaminationAnswer],
        evaluations: list[SatisfactionEvaluation],
        reflections: list[Reflection],
    ) -> str:
        lines: list[str] = ["ROUND 1 — Independent analysis:"]
        lines.extend(
            (
                f"- {verdict.member_name}: {verdict.vote} "
                f"({verdict.confidence}%). Reason: {verdict.core_reason}. "
                f"Risk: {verdict.main_risk}."
            )
            for verdict in verdicts
        )

        lines.append("\nROUND 2 — Cross-examination:")
        if answers:
            lines.extend(
                (
                    f"- {answer.asker_name} asked {answer.target_name}: "
                    f"{answer.question} Answer: {answer.answer}"
                )
                for answer in answers
            )
        else:
            lines.append("- No routed questions.")

        lines.append("\nROUND 3 — Satisfaction evaluation:")
        if evaluations:
            lines.extend(
                (
                    f"- {evaluation.asker_name} evaluated {evaluation.target_name}: "
                    f"{evaluation.satisfaction}. Reason: {evaluation.reason}. "
                    f"Confidence delta: {evaluation.confidence_delta:+d}."
                )
                for evaluation in evaluations
            )
        else:
            lines.append("- No evaluations.")

        lines.append("\nROUND 4 — Reflection:")
        lines.extend(
            (
                f"- {reflection.member_name}: {reflection.vote_before} "
                f"({reflection.confidence_before}%) -> {reflection.vote_after} "
                f"({reflection.confidence_after}%). Learned: {reflection.learned}. "
                f"Reason: {reflection.reason}."
            )
            for reflection in reflections
        )

        return "\n".join(lines)

    def _answer_question(
        self,
        question: RoutedQuestion,
        proposition: str,
        verdicts: list[Verdict],
    ) -> CrossExaminationAnswer:
        target = self._member_by_name(question.target_name)
        model = self.models[target.name]

        user_prompt = ANSWER_INSTRUCTION.format(
            proposition=proposition,
            council_context=self._council_context(verdicts),
            asker_name=question.asker_name,
            question=question.question,
        )

        if self.mock:
            raw = mock_answer(target.name, question.question, user_prompt)
            model = "mock"
        else:
            s = target.sampling
            raw = chat(
                model=model,
                system=target.persona,
                user=user_prompt,
                temperature=s.temperature,
                top_p=s.top_p,
                repeat_penalty=s.repeat_penalty,
                response_format="json",
            )

        return parse_cross_examination_answer(
            question=question,
            raw=raw,
            model=model,
        )

    def cross_examination(
        self,
        proposition: str,
        verdicts: list[Verdict],
    ) -> tuple[list[RoutedQuestion], list[CrossExaminationAnswer]]:
        """Route questions and collect answers from addressed members."""
        questions = collect_questions(verdicts)

        if not questions:
            return questions, []

        with ThreadPoolExecutor(max_workers=len(questions)) as pool:
            answers = list(
                pool.map(
                    lambda question: self._answer_question(
                        question=question,
                        proposition=proposition,
                        verdicts=verdicts,
                    ),
                    questions,
                )
            )

        return questions, answers

    def _evaluate_answer(
        self,
        answer: CrossExaminationAnswer,
        proposition: str,
    ) -> SatisfactionEvaluation:
        asker = self._member_by_name(answer.asker_name)
        model = self.models[asker.name]

        user_prompt = EVALUATION_INSTRUCTION.format(
            proposition=proposition,
            target_name=answer.target_name,
            question=answer.question,
            answer=answer.answer,
        )

        if self.mock:
            raw = mock_evaluation(asker.name, answer.answer, user_prompt)
            model = "mock"
        else:
            s = asker.sampling
            raw = chat(
                model=model,
                system=asker.persona,
                user=user_prompt,
                temperature=s.temperature,
                top_p=s.top_p,
                repeat_penalty=s.repeat_penalty,
                response_format="json",
            )

        return parse_satisfaction_evaluation(
            answer=answer,
            raw=raw,
            model=model,
        )

    def satisfaction_evaluation(
        self,
        proposition: str,
        answers: list[CrossExaminationAnswer],
    ) -> list[SatisfactionEvaluation]:
        """Ask original questioners to evaluate whether answers satisfied them."""
        if not answers:
            return []

        with ThreadPoolExecutor(max_workers=len(answers)) as pool:
            return list(
                pool.map(
                    lambda answer: self._evaluate_answer(
                        answer=answer,
                        proposition=proposition,
                    ),
                    answers,
                )
            )

    def _reflect_member(
        self,
        member: CouncilMember,
        proposition: str,
        verdicts: list[Verdict],
        answers: list[CrossExaminationAnswer],
        evaluations: list[SatisfactionEvaluation],
    ) -> Reflection:
        verdict = self._verdict_by_member(verdicts, member.name)
        model = self.models[member.name]

        user_prompt = REFLECTION_INSTRUCTION.format(
            proposition=proposition,
            vote_before=verdict.vote,
            confidence_before=verdict.confidence,
            core_reason=verdict.core_reason,
            main_risk=verdict.main_risk,
            change_condition=verdict.can_change_mind_if,
            deliberation_context=self._deliberation_context(answers, evaluations),
        )

        if self.mock:
            raw = mock_reflection(
                member.name,
                verdict.vote,
                verdict.confidence,
                user_prompt,
            )
            model = "mock"
        else:
            s = member.sampling
            raw = chat(
                model=model,
                system=member.persona,
                user=user_prompt,
                temperature=s.temperature,
                top_p=s.top_p,
                repeat_penalty=s.repeat_penalty,
                response_format="json",
            )

        return parse_reflection(
            member=member,
            verdict=verdict,
            raw=raw,
            model=model,
        )

    def reflection_round(
        self,
        proposition: str,
        verdicts: list[Verdict],
        answers: list[CrossExaminationAnswer],
        evaluations: list[SatisfactionEvaluation],
    ) -> list[Reflection]:
        """Run reflection for every council member."""
        with ThreadPoolExecutor(max_workers=len(COUNCIL)) as pool:
            return list(
                pool.map(
                    lambda member: self._reflect_member(
                        member=member,
                        proposition=proposition,
                        verdicts=verdicts,
                        answers=answers,
                        evaluations=evaluations,
                    ),
                    COUNCIL,
                )
            )

    def chair_dossier(
        self,
        proposition: str,
        verdicts: list[Verdict],
        answers: list[CrossExaminationAnswer],
        evaluations: list[SatisfactionEvaluation],
        reflections: list[Reflection],
        decision: dict,
    ) -> DecisionDossier:
        """Generate a non-voting Chair decision dossier."""
        vote_split = f"{decision['affirmative']} affirmative / {decision['negative']} negative"
        model = self.chair_model

        final_vote_record = build_structured_chair_record(reflections)

        user_prompt = CHAIR_INSTRUCTION.format(
            proposition=proposition,
            decision=decision["decision"],
            vote_split=vote_split,
            final_vote_record=final_vote_record,
            council_record=self._council_record(
                verdicts=verdicts,
                answers=answers,
                evaluations=evaluations,
                reflections=reflections,
            ),
        )

        if self.mock:
            raw = mock_chair_dossier(decision["decision"], vote_split, user_prompt)
            model = "mock"
        else:
            raw = chat(
                model=model,
                system=(
                    "You are the non-voting Chair of MAGI. "
                    "You summarize faithfully. You do not add a new vote."
                ),
                user=user_prompt,
                temperature=CHAIR_SAMPLING.temperature,
                top_p=CHAIR_SAMPLING.top_p,
                repeat_penalty=CHAIR_SAMPLING.repeat_penalty,
                response_format="json",
            )

        return parse_decision_dossier(
            raw=raw,
            model=model,
            fallback_decision=decision["decision"],
            fallback_split=vote_split,
        )

    def deliberate(self, proposition: str) -> dict:
        """Run the current council protocol."""
        self._progress("Round 1/5 — independent analysis")
        verdicts = self.independent_analysis(proposition)

        self._progress("Round 2/5 — cross-examination")
        questions, answers = self.cross_examination(
            proposition=proposition,
            verdicts=verdicts,
        )

        self._progress("Round 3/5 — satisfaction evaluation")
        evaluations = self.satisfaction_evaluation(
            proposition=proposition,
            answers=answers,
        )

        self._progress("Round 4/5 — reflection")
        reflections = self.reflection_round(
            proposition=proposition,
            verdicts=verdicts,
            answers=answers,
            evaluations=evaluations,
        )

        self._progress("Decision — tallying reflected votes")
        decision = decide_reflections(reflections)

        self._progress("Round 5/5 — chair dossier")
        dossier = self.chair_dossier(
            proposition=proposition,
            verdicts=verdicts,
            answers=answers,
            evaluations=evaluations,
            reflections=reflections,
            decision=decision,
        )

        return {
            "proposition": proposition,
            "verdicts": verdicts,
            "questions": questions,
            "answers": answers,
            "evaluations": evaluations,
            "reflections": reflections,
            "decision": decision,
            "dossier": dossier,
            "model_notes": self.model_notes,
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


def decide_reflections(reflections: list[Reflection]) -> dict:
    """Decide by simple majority after reflection."""
    affirmative = [reflection for reflection in reflections if reflection.approves]
    negative = [reflection for reflection in reflections if not reflection.approves]

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
