"""MAGI council execution engine."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from magi.chair.dossier import DecisionDossier, parse_decision_dossier
from magi.chair.record import build_structured_chair_record
from magi.council.members import CHAIR_SAMPLING, COUNCIL, CouncilMember
from magi.council.verdict import ABSTAIN, INVALID_QUESTION, NO_CONSENSUS, OPPOSE, SUPPORT, Verdict, parse_verdict
from magi.tools import telemetry
from magi.protocol.ireul import neutralized_proposition, scan_proposition
from magi.protocol.gravity import (
    ROUTINE,
    gravity_threshold_note,
    normalize_stakes,
    rule_for,
)
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
from magi.utils.json_tools import extract_json_object, text_field


DEFAULT_MODEL = "llama3.2"

VERDICT_REPAIR_INSTRUCTION = """
Your previous Round 1 MAGI verdict JSON failed strict validation.

Validation error:
{error}

Original proposition:
{proposition}

Rejected output:
{raw}

Repair task:
Return ONLY one corrected JSON object.
No prose, no markdown, no comments, no trailing text.

You must use the same Round 1 schema:
target_action
core_reason
main_risk
question_for
question
can_change_mind_if
stance_summary
vote_reason_alignment
action_causality
counterfactual_comparison
vote
confidence

Core ballot semantics:
- SUPPORT means: take / perform / preserve / allow / adopt the target action.
- OPPOSE means: do not take / reject / avoid / refuse the target action.
- ABSTAIN means: the evidence or comparison is genuinely unclear.
- INVALID_QUESTION means: the proposition has no stable target action or is malformed.
- Do not confuse "I value X" with OPPOSE when the target action is "preserve X".
- If the target action is "preserve minority reports" and you believe minority reports contain valuable dissent, your vote should be SUPPORT.
- If the target action is "delete minority reports" and you believe minority reports contain valuable dissent, your vote should be OPPOSE.
- Before returning JSON, ask yourself: "Does my core_reason actually support my vote about TAKING the target action?"
- If your reason supports taking the target action, vote SUPPORT.
- If your reason supports not taking the target action, vote OPPOSE.

Consistency rules:
- vote must be one of SUPPORT, OPPOSE, ABSTAIN, INVALID_QUESTION.
- stance_summary must match vote.
- vote_reason_alignment must match vote.
- action_causality must describe the direct consequence of TAKING the target action.
- counterfactual_comparison must compare TAKING the target action versus NOT TAKING it.
- If taking the target action is better than not taking it, vote should be SUPPORT.
- If taking the target action is worse than not taking it, vote should be OPPOSE.
- If the comparison is unclear, vote should be ABSTAIN.
- If the target action is malformed or ambiguous, vote should be INVALID_QUESTION.
- Do not justify OPPOSE using delay, hesitation, inaction, failure to act, or waiting.
- For OPPOSE, harm must be caused by TAKING the target action.
- For SUPPORT, benefit must be caused by TAKING the target action.

Preserve your council identity and core concern, but correct any contradiction between vote, causality, and counterfactual comparison.
"""


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

Ballot semantics:
- SUPPORT means you support the concrete target action as stated.
- OPPOSE means you oppose the concrete target action as stated.
- ABSTAIN means the available information is insufficient to support or oppose.
- INVALID_QUESTION means the proposition is malformed, ambiguous, a false dilemma, or not a concrete action.
- The stance_summary must not contradict the vote.
- If vote is SUPPORT, stance_summary must start with: I SUPPORT
- If vote is OPPOSE, stance_summary must start with: I OPPOSE
- If vote is ABSTAIN, stance_summary must start with: I ABSTAIN
- If vote is INVALID_QUESTION, stance_summary must start with: I REJECT THE QUESTION
- vote_reason_alignment must explicitly connect the vote to the reason.
- If vote is SUPPORT, vote_reason_alignment must start with: I SUPPORT THE TARGET ACTION BECAUSE
- If vote is OPPOSE, vote_reason_alignment must start with: I OPPOSE THE TARGET ACTION BECAUSE
- If vote is ABSTAIN, vote_reason_alignment must start with: I ABSTAIN BECAUSE
- If vote is INVALID_QUESTION, vote_reason_alignment must start with: I REJECT THE QUESTION BECAUSE
- action_causality must describe the direct consequence of TAKING the target action.
- action_causality must not describe delay, hesitation, inaction, failure to act, or waiting.
- If vote is SUPPORT, action_causality must start with: IF THE TARGET ACTION IS TAKEN, THEN IT HELPS BECAUSE
- If vote is OPPOSE, action_causality must start with: IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE
- If vote is ABSTAIN, action_causality must start with: IF THE TARGET ACTION IS TAKEN, THEN THE EFFECT IS UNCLEAR BECAUSE
- If vote is INVALID_QUESTION, action_causality must start with: THE TARGET ACTION IS NOT WELL-DEFINED BECAUSE
- If vote is SUPPORT, counterfactual_comparison must start with: TAKING THE TARGET ACTION IS BETTER THAN NOT TAKING IT BECAUSE
- If vote is OPPOSE, counterfactual_comparison must start with: TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE
- If vote is ABSTAIN, counterfactual_comparison must start with: I CANNOT COMPARE TAKING VS NOT TAKING THE TARGET ACTION BECAUSE
- If vote is INVALID_QUESTION, counterfactual_comparison must start with: I CANNOT COMPARE OPTIONS BECAUSE THE QUESTION IS INVALID

Reason before you vote.
First identify the target_action. Then write the reason. Your vote comes LAST, and it must follow from
the core_reason you have just written. Do not decide first and justify afterwards.

Return ONLY one valid JSON object.
No prose, no markdown, no comments, no trailing text.
All string values must be plain text.

Required schema (emit the keys in this exact order):
{{
  "target_action": "the concrete action being judged, or the ambiguity if the question is malformed",
  "core_reason": "one concrete reason, written in your council voice",
  "main_risk": "one concrete failure mode or danger",
  "question_for": "MELCHIOR" | "BALTHASAR" | "CASPER" | "ARTABAN" | "NO QUESTIONS",
  "question": "one sharp question to another member, or NO QUESTIONS",
  "can_change_mind_if": "specific evidence, condition, or argument that could change your vote",
  "stance_summary": "must start with exactly one matching phrase: I SUPPORT / I OPPOSE / I ABSTAIN / I REJECT THE QUESTION, then explain what your vote means",
  "vote_reason_alignment": "must start with exactly one matching phrase: I SUPPORT THE TARGET ACTION BECAUSE / I OPPOSE THE TARGET ACTION BECAUSE / I ABSTAIN BECAUSE / I REJECT THE QUESTION BECAUSE, then connect the vote to core_reason",
  "action_causality": "must describe the direct consequence of TAKING the target action, using the required prefix for your vote",
  "counterfactual_comparison": "must compare taking the target action versus not taking it, using the required prefix for your vote",
  "vote": "SUPPORT" | "OPPOSE" | "ABSTAIN" | "INVALID_QUESTION",
  "confidence": 0-100
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

Write your reason first. Your satisfaction rating must follow from the reason you just wrote.

Required schema (emit the keys in this exact order):
{{
  "reason": "one or two sentences explaining your evaluation",
  "satisfaction": "SATISFIED" | "PARTIALLY SATISFIED" | "NOT SATISFIED",
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

Write "learned" and "reason" first. Your vote comes LAST and must follow from the reason you
just wrote. Do not decide first and justify afterwards.

Required schema (emit the keys in this exact order):
{{
  "learned": "one or two sentences about what changed in your understanding",
  "reason": "one or two sentences explaining why your vote/confidence changed or stayed the same",
  "vote_after_reflection": "SUPPORT" | "OPPOSE" | "ABSTAIN" | "INVALID_QUESTION",
  "confidence_after_reflection": 0-100
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
Do not attribute SUPPORT reasoning to a member whose final reflected vote is OPPOSE, or OPPOSE reasoning to a member whose final reflected vote is SUPPORT. Treat ABSTAIN and INVALID_QUESTION as distinct positions, not as hidden opposition.

Dossier rules:
- Base vote attribution on the authoritative final reflected vote record, not on inference from prose.
- Use the FINAL POSITION GROUPS section exactly when deciding who belongs to SUPPORT, OPPOSE, ABSTAIN, or INVALID_QUESTION.
- If the decision is SUPPORT, majority_reasoning must summarize only SUPPORT members.
- If the decision is OPPOSE, majority_reasoning must summarize only OPPOSE members.
- If the decision is INVALID_QUESTION, majority_reasoning must explain why the question framing was rejected.
- If the decision is NO CONSENSUS, state that no majority exists and summarize the unresolved competing final positions.
- minority_reasoning must summarize members not in the winning decision group.
- Never place a SUPPORT member in OPPOSE reasoning, or an OPPOSE member in SUPPORT reasoning.
- Treat ABSTAIN as uncertainty/insufficient information, not as hidden opposition.
- Treat INVALID_QUESTION as rejection of the proposition framing, not as opposition to the underlying value.
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
  "decision": "SUPPORT" | "OPPOSE" | "INVALID_QUESTION" | "NO CONSENSUS",
  "vote_split": "text summary of the final vote split",
  "majority_reasoning": "summary based on final reflected votes only; if NO CONSENSUS: state that no majority exists and summarize the competing final positions",
  "minority_reasoning": "summary based on final reflected votes only; if NO CONSENSUS: summarize the unresolved opposing final positions",
  "key_risks": "main risks identified by the council",
  "outstanding_uncertainties": "what remains unresolved, or: None identified in the council record",
  "required_conditions": "conditions under which the decision should be accepted, or: None identified in the council record",
  "recommended_next_action": "one concrete next step"
}}
"""


SEMANTIC_FIELD_CHECK_INSTRUCTION = """
You are a strict semantic direction checker.

Classify what this single reasoning text supports relative to the target action.

Return ONLY JSON:
{{
  "relation": "SUPPORTS_TAKING" | "SUPPORTS_NOT_TAKING" | "UNCLEAR",
  "explanation": "brief reason"
}}

Definitions:
- SUPPORTS_TAKING means the text supports taking / performing / preserving / allowing / adopting the target action.
- SUPPORTS_NOT_TAKING means the text supports rejecting / avoiding / deleting / not performing the target action.
- UNCLEAR means the text is mixed, irrelevant, or does not clearly support either side.

Examples:
- Target action: "preserve minority reports"
  Text: "minority reports contain valuable dissent and prevent groupthink"
  relation: SUPPORTS_TAKING

- Target action: "preserve minority reports"
  Text: "preserving them adds clutter and reduces clarity"
  relation: SUPPORTS_NOT_TAKING

- Target action: "delete minority reports"
  Text: "minority reports contain valuable dissent and prevent groupthink"
  relation: SUPPORTS_NOT_TAKING

- Target action: "delete minority reports"
  Text: "deleting them improves speed and clarity"
  relation: SUPPORTS_TAKING

Target action:
{target_action}

Reasoning text:
{text}
"""


VERDICT_SEMANTIC_CHECK_INSTRUCTION = """
You are a strict semantic ballot checker.

Your task is NOT to decide the proposition yourself.
Your task is only to classify what the member's stated reasoning supports.

Return ONLY JSON:
{{
  "relation": "SUPPORTS_TAKING" | "SUPPORTS_NOT_TAKING" | "UNCLEAR",
  "explanation": "brief reason"
}}

Definitions:
- SUPPORTS_TAKING means the reasoning supports taking / performing / preserving / allowing / adopting the target action.
- SUPPORTS_NOT_TAKING means the reasoning supports rejecting / avoiding / deleting / not performing the target action.
- UNCLEAR means the reasoning does not clearly support either side.

Important examples:
- Target action: "preserve minority reports"
  Reasoning: "minority reports contain valuable dissent and prevent groupthink"
  relation: SUPPORTS_TAKING

- Target action: "delete minority reports"
  Reasoning: "minority reports contain valuable dissent and prevent groupthink"
  relation: SUPPORTS_NOT_TAKING

- Target action: "attempt to save humans from extinction"
  Reasoning: "inaction will cause human extinction"
  relation: SUPPORTS_TAKING

- Target action: "attempt to save humans from extinction"
  Reasoning: "the intervention will cause catastrophic harm"
  relation: SUPPORTS_NOT_TAKING

Do not trust the member's vote label.

Classify only the semantic direction of the target_action, core_reason, main_risk, vote_reason_alignment, action_causality, and counterfactual_comparison.

Strict consistency rule:
- If some reasoning fields support taking the target action but other fields support not taking it, return UNCLEAR.
- If the reasoning is internally mixed or self-contradictory, return UNCLEAR.
- Return SUPPORTS_TAKING only when the reasoning clearly supports taking the target action.
- Return SUPPORTS_NOT_TAKING only when the reasoning clearly supports not taking the target action.

Proposition:
{proposition}

Target action:
{target_action}

Member vote:
{vote}

Member reasoning fields:
core_reason: {core_reason}
main_risk: {main_risk}
vote_reason_alignment: {vote_reason_alignment}
action_causality: {action_causality}
counterfactual_comparison: {counterfactual_comparison}
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
        event_sink: Callable[[dict], None] | None = None,
    ) -> None:
        self.mock = mock
        self.default_model = default_model
        self.progress = progress
        # event_sink receives structured events for live views. Defaults to a
        # no-op so every existing run is byte-for-byte unchanged.
        self.event_sink = event_sink
        self.model_notes: list[str] = []

        self.models = self._resolve_models(model=model, same=same)
        self.chair_model = "mock" if mock else self._resolve_chair_model(model=model)

    def _progress(self, message: str) -> None:
        """Emit a progress message if a progress callback is configured."""
        if self.progress:
            self.progress(message)

    def _emit(self, event: dict) -> None:
        """Emit a structured event to the live sink, if one is configured.

        Never raises into the protocol: a broken UI must not break a deliberation.
        """
        if self.event_sink:
            try:
                self.event_sink(event)
            except Exception:
                pass

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

    def _semantic_text_relation(
        self,
        target_action: str,
        text: str,
        model: str,
    ) -> str:
        if self.mock:
            return "UNCLEAR"

        prompt = SEMANTIC_FIELD_CHECK_INSTRUCTION.format(
            target_action=target_action,
            text=text,
        )

        try:
            raw = chat(
                model=model,
                system="You are a neutral deterministic semantic validator. Do not deliberate. Only classify.",
                user=prompt,
                temperature=0.0,
                top_p=1.0,
                repeat_penalty=1.0,
                response_format="json",
            )
            obj = extract_json_object(raw)
            relation = text_field(obj, raw, "relation", "UNCLEAR").strip().upper()
        except Exception:
            return "UNCLEAR"

        if relation in {"SUPPORTS_TAKING", "SUPPORTS_NOT_TAKING", "UNCLEAR"}:
            return relation

        return "UNCLEAR"

    def _semantic_vote_relation(
        self,
        member: CouncilMember,
        proposition: str,
        verdict: Verdict,
        model: str,
    ) -> str:
        if self.mock or verdict.vote not in {SUPPORT, OPPOSE}:
            return "UNCLEAR"

        prompt = VERDICT_SEMANTIC_CHECK_INSTRUCTION.format(
            proposition=proposition,
            target_action=verdict.target_action,
            vote=verdict.vote,
            core_reason=verdict.core_reason,
            main_risk=verdict.main_risk,
            vote_reason_alignment=verdict.vote_reason_alignment,
            action_causality=verdict.action_causality,
            counterfactual_comparison=verdict.counterfactual_comparison,
        )

        try:
            raw = chat(
                model=model,
                system="You are a neutral deterministic semantic validator. Do not deliberate. Only classify.",
                user=prompt,
                temperature=0.0,
                top_p=1.0,
                repeat_penalty=1.0,
                response_format="json",
            )
            obj = extract_json_object(raw)
            relation = text_field(obj, raw, "relation", "UNCLEAR").strip().upper()
        except Exception:
            return "UNCLEAR"

        if relation in {"SUPPORTS_TAKING", "SUPPORTS_NOT_TAKING", "UNCLEAR"}:
            return relation

        return "UNCLEAR"

    def _assert_semantic_vote_alignment(
        self,
        member: CouncilMember,
        proposition: str,
        verdict: Verdict,
        model: str,
    ) -> None:
        if self.mock or verdict.vote not in {SUPPORT, OPPOSE}:
            return

        relation = self._semantic_vote_relation(member, proposition, verdict, model)
        core_relation = self._semantic_text_relation(
            verdict.target_action,
            verdict.core_reason,
            model,
        )

        if verdict.vote == SUPPORT:
            if relation == "SUPPORTS_NOT_TAKING" or core_relation == "SUPPORTS_NOT_TAKING":
                raise ValueError(
                    "Semantic vote check contradicted SUPPORT: the reasoning "
                    "supports not taking the target action."
                )

        if verdict.vote == OPPOSE:
            if relation == "SUPPORTS_TAKING" or core_relation == "SUPPORTS_TAKING":
                raise ValueError(
                    "Semantic vote check contradicted OPPOSE: the reasoning "
                    "supports taking the target action."
                )

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

        def invalid_ballot_abstention(error: ValueError, rejected_raw: str) -> Verdict:
            reason = (
                f"{member.name} produced an internally inconsistent ballot after "
                f"validation repair: {error}"
            )
            return Verdict(
                member_name=member.name,
                member_title=member.title,
                vote=ABSTAIN,
                confidence=0,
                target_action=proposition,
                core_reason=reason,
                main_risk="Invalid member ballot excluded from decisive tally.",
                question_for="NO QUESTIONS",
                question="NO QUESTIONS",
                can_change_mind_if="A coherent, schema-valid ballot is produced.",
                stance_summary="I ABSTAIN because my previous ballot was internally inconsistent.",
                vote_reason_alignment="I ABSTAIN BECAUSE my previous ballot was internally inconsistent.",
                action_causality=(
                    "IF THE TARGET ACTION IS TAKEN, THEN THE EFFECT IS UNCLEAR BECAUSE "
                    "this member did not produce a coherent validated assessment."
                ),
                counterfactual_comparison=(
                    "I CANNOT COMPARE TAKING VS NOT TAKING THE TARGET ACTION BECAUSE "
                    "this member did not produce a coherent validated assessment."
                ),
                raw=rejected_raw,
                model=model,
            )

        max_attempts = 3

        for attempt in range(max_attempts):
            try:
                verdict = parse_verdict(member=member, raw=raw, model=model)
                self._assert_semantic_vote_alignment(
                    member,
                    proposition,
                    verdict,
                    model,
                )
                if attempt > 0:
                    telemetry.record_repair_success(member.name)
                return verdict
            except ValueError as error:
                if self.mock:
                    raise

                telemetry.record_failure(member.name, error)

                if attempt == max_attempts - 1:
                    telemetry.record_quarantine(member.name, error)
                    return invalid_ballot_abstention(error, raw)

                telemetry.record_repair_attempt(member.name)

                repair_prompt = VERDICT_REPAIR_INSTRUCTION.format(
                    error=str(error),
                    proposition=proposition,
                    raw=raw,
                )

                s = member.sampling
                raw = chat(
                    model=model,
                    system=member.persona,
                    user=repair_prompt,
                    temperature=0.0,
                    top_p=1.0,
                    repeat_penalty=s.repeat_penalty,
                    response_format="json",
                )

        raise RuntimeError("unreachable verdict repair state")

    def independent_analysis(self, proposition: str) -> list[Verdict]:
        """Run independent council analysis."""
        def _resolve(member: CouncilMember) -> Verdict:
            self._emit({"type": "member_started", "member": member.name})
            verdict = self._ask_member(member, proposition)
            self._emit({
                "type": "member_resolved",
                "member": verdict.member_name,
                "vote": verdict.vote,
                "confidence": verdict.confidence,
                "reason": verdict.core_reason,
            })
            return verdict

        with ThreadPoolExecutor(max_workers=len(COUNCIL)) as pool:
            return list(pool.map(_resolve, COUNCIL))

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

        if self._is_quarantined_invalid_ballot(verdict):
            return self._locked_invalid_reflection(verdict)

        reflection = parse_reflection(
            member=member,
            verdict=verdict,
            raw=raw,
            model=model,
        )
        return self._validated_reflection(verdict, reflection, model)

    def _validated_reflection(
        self,
        verdict: Verdict,
        reflection: Reflection,
        model: str,
    ) -> Reflection:
        if self.mock or reflection.vote_after not in {SUPPORT, OPPOSE}:
            return reflection

        relation = self._semantic_text_relation(
            verdict.target_action,
            reflection.reason,
            model,
        )

        held_vote = reflection.vote_after == verdict.vote

        # A HELD vote was already validated by the full Round-1 ballot pipeline.
        # Reflecting on a hold naturally reads as "I learned X and my position
        # stands" — enrichment, not a fresh directional argument — so the checker
        # returns UNCLEAR. Freezing that discards a valid reflection (this is what
        # left MELCHIOR and BALTHASAR frozen at 85 while CASPER, whose reason
        # happened to be explicitly directional, passed). Accept a hold unless the
        # reason POSITIVELY argues the opposite direction, which would be a latent
        # inversion worth catching.
        if held_vote:
            opposite = (
                "SUPPORTS_NOT_TAKING" if reflection.vote_after == SUPPORT
                else "SUPPORTS_TAKING"
            )
            if relation == opposite:
                return self._preserved_reflection(
                    verdict,
                    reflection,
                    "Reflection reason argued against the held vote. "
                    "Preserving the validated Round 1 vote.",
                )
            return reflection

        # A CHANGED vote is a strong claim — the debate moved the member — so it
        # must be gated: the reason has to actively support the new direction.
        if reflection.vote_after == SUPPORT and relation == "SUPPORTS_TAKING":
            return reflection

        if reflection.vote_after == OPPOSE and relation == "SUPPORTS_NOT_TAKING":
            return reflection

        return self._preserved_reflection(
            verdict,
            reflection,
            "Reflection reason did not semantically support the changed vote. "
            "Preserving the validated Round 1 vote.",
        )

    def _preserved_reflection(
        self,
        verdict: Verdict,
        reflection: Reflection,
        reason: str,
    ) -> Reflection:
        return Reflection(
            member_name=reflection.member_name,
            member_title=reflection.member_title,
            vote_before=reflection.vote_before,
            vote_after=verdict.vote,
            confidence_before=reflection.confidence_before,
            confidence_after=verdict.confidence,
            learned=reflection.learned,
            reason=reason,
            model=reflection.model,
            raw=reflection.raw,
        )

    def _is_quarantined_invalid_ballot(self, verdict: Verdict) -> bool:
        return (
            verdict.vote == ABSTAIN
            and verdict.confidence == 0
            and "internally inconsistent ballot" in verdict.core_reason
        )

    def _locked_invalid_reflection(self, verdict: Verdict) -> Reflection:
        return Reflection(
            member_name=verdict.member_name,
            member_title=verdict.member_title,
            vote_before=verdict.vote,
            vote_after=ABSTAIN,
            confidence_before=verdict.confidence,
            confidence_after=0,
            learned="This member's Round 1 ballot was quarantined as internally inconsistent.",
            reason="Quarantined invalid ballots cannot re-enter the decisive tally during reflection.",
            model=verdict.model,
            raw=verdict.raw,
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
        vote_split = (
            f"{decision['support']} support / "
            f"{decision['oppose']} oppose / "
            f"{decision['abstain']} abstain / "
            f"{decision['invalid_question']} invalid-question"
        )
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

    def deliberate(self, proposition: str, stakes: str = ROUTINE) -> dict:
        """Run the current council protocol.

        stakes raises the agreement bar (see magi.protocol.gravity): ROUTINE is a
        simple majority, SERIOUS forbids dissent, GRAVE requires the whole council.
        """
        stakes = normalize_stakes(stakes)

        self._emit({
            "type": "run_started",
            "proposition": proposition,
            "stakes": stakes,
            "members": [m.name for m in COUNCIL],
            "models": {m.name: self.models.get(m.name, "") for m in COUNCIL},
        })

        # Ireul: scan the proposition for structural manipulation before the
        # council sees it. If adversarial, members judge a neutralized form and
        # the attempt is named in the record rather than hidden.
        ireul_report = scan_proposition(proposition)
        working_proposition = neutralized_proposition(proposition, ireul_report)
        if ireul_report.is_adversarial:
            self._progress("Ireul — manipulation detected in proposition")
            self._emit({
                "type": "ireul_alert",
                "categories": sorted(ireul_report.categories),
                "summary": ireul_report.summary(),
            })
        self._progress("Round 1/5 — independent analysis")
        self._emit({"type": "round_started", "round": 1, "name": "independent_analysis"})
        verdicts = self.independent_analysis(working_proposition)

        self._progress("Round 2/5 — cross-examination")
        self._emit({"type": "round_started", "round": 2, "name": "cross_examination"})
        questions, answers = self.cross_examination(
            proposition=working_proposition,
            verdicts=verdicts,
        )

        self._progress("Round 3/5 — satisfaction evaluation")
        self._emit({"type": "round_started", "round": 3, "name": "satisfaction_evaluation"})
        evaluations = self.satisfaction_evaluation(
            proposition=working_proposition,
            answers=answers,
        )

        self._progress("Round 4/5 — reflection")
        self._emit({"type": "round_started", "round": 4, "name": "reflection"})
        reflections = self.reflection_round(
            proposition=working_proposition,
            verdicts=verdicts,
            answers=answers,
            evaluations=evaluations,
        )
        for r in reflections:
            self._emit({
                "type": "reflection_resolved",
                "member": r.member_name,
                "from": r.vote_before,
                "to": r.vote_after,
                "confidence": r.confidence_after,
                "reason": r.reason,
            })

        self._progress("Decision — tallying reflected votes")
        decision = decide_reflections(reflections, stakes=stakes)
        self._emit({
            "type": "decision",
            "decision": decision["decision"],
            "support": decision["support"],
            "oppose": decision["oppose"],
            "abstain": decision["abstain"],
            "invalid_question": decision["invalid_question"],
            "stakes": stakes,
            "gravity_note": decision.get("gravity_note", ""),
        })

        self._progress("Round 5/5 — chair dossier")
        self._emit({"type": "round_started", "round": 5, "name": "chair_dossier"})
        dossier = self.chair_dossier(
            proposition=working_proposition,
            verdicts=verdicts,
            answers=answers,
            evaluations=evaluations,
            reflections=reflections,
            decision=decision,
        )

        self._emit({"type": "run_finished", "decision": decision["decision"]})

        return {
            "proposition": proposition,
            "stakes": stakes,
            "ireul": {
                "adversarial": ireul_report.is_adversarial,
                "categories": sorted(ireul_report.categories),
                "summary": ireul_report.summary(),
            },
            "verdicts": verdicts,
            "questions": questions,
            "answers": answers,
            "evaluations": evaluations,
            "reflections": reflections,
            "decision": decision,
            "dossier": dossier,
            "model_notes": self.model_notes,
        }


def _vote_value(item: object) -> str:
    if hasattr(item, "vote_after"):
        return item.vote_after
    return item.vote


def _decide_from_votes(votes: list[str]) -> dict:
    """Decide using explicit ballot semantics.

    ABSTAIN is not treated as hidden opposition.
    INVALID_QUESTION can itself become the decision if it has a majority.
    SUPPORT and OPPOSE are compared only as directional votes.
    """
    support = sum(1 for vote in votes if vote == SUPPORT)
    oppose = sum(1 for vote in votes if vote == OPPOSE)
    abstain = sum(1 for vote in votes if vote == ABSTAIN)
    invalid_question = sum(1 for vote in votes if vote == INVALID_QUESTION)
    total = len(votes)

    if invalid_question > total / 2:
        decision = INVALID_QUESTION
    elif support > oppose:
        decision = SUPPORT
    elif oppose > support:
        decision = OPPOSE
    else:
        decision = NO_CONSENSUS

    return {
        "decision": decision,
        "support": support,
        "oppose": oppose,
        "abstain": abstain,
        "invalid_question": invalid_question,
    }


def decide(verdicts: list[Verdict]) -> dict:
    support = sum(v.supports for v in verdicts)
    oppose = sum(v.opposes for v in verdicts)
    abstain = sum(v.abstains for v in verdicts)
    invalid_question = sum(v.invalid_question for v in verdicts)

    return {
        "decision": _decision_from_split(
            support,
            oppose,
            abstain,
            invalid_question,
        ),
        "support": support,
        "oppose": oppose,
        "abstain": abstain,
        "invalid_question": invalid_question,
    }




def _decision_from_split(
    support: int,
    oppose: int,
    abstain: int,
    invalid_question: int,
    stakes: str = ROUTINE,
) -> str:
    council_size = support + oppose + abstain + invalid_question
    decisive_total = support + oppose
    quorum = (council_size // 2) + 1 if council_size else 1

    rule = rule_for(stakes)

    if invalid_question >= quorum:
        return INVALID_QUESTION

    # Base quorum: enough members must have taken a position at all.
    if decisive_total < quorum:
        return NO_CONSENSUS

    winner, winning_count = (
        (SUPPORT, support) if support > oppose
        else (OPPOSE, oppose) if oppose > support
        else (NO_CONSENSUS, 0)
    )

    if winner == NO_CONSENSUS:
        return NO_CONSENSUS

    # --- Decision gravity: raise the bar as stakes rise. Never lower it. ---

    # GRAVE: any abstention means the full council did not weigh in — block.
    if rule.block_on_abstention and (abstain > 0 or invalid_question > 0):
        return NO_CONSENSUS

    # SERIOUS+: no dissent tolerated among members who took a position.
    if rule.forbid_dissent and support > 0 and oppose > 0:
        return NO_CONSENSUS

    # GRAVE: the entire council must be on the winning side.
    if rule.require_full_council_agreement and winning_count < council_size:
        return NO_CONSENSUS

    return winner


def decide_reflections(reflections: list[Reflection], stakes: str = ROUTINE) -> dict:
    support = sum(r.supports for r in reflections)
    oppose = sum(r.opposes for r in reflections)
    abstain = sum(r.abstains for r in reflections)
    invalid_question = sum(r.invalid_question for r in reflections)
    council_size = support + oppose + abstain + invalid_question

    stakes = normalize_stakes(stakes)

    return {
        "decision": _decision_from_split(
            support,
            oppose,
            abstain,
            invalid_question,
            stakes=stakes,
        ),
        "support": support,
        "oppose": oppose,
        "abstain": abstain,
        "invalid_question": invalid_question,
        "stakes": stakes,
        "gravity_note": gravity_threshold_note(stakes, council_size),
    }


