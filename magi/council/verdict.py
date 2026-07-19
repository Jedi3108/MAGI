"""Council verdict structures and parsing."""

from __future__ import annotations

import re
from dataclasses import dataclass

from magi.council.members import CouncilMember, VALID_MEMBER_NAMES
from magi.utils.json_tools import extract_json_object, int_field, text_field

SUPPORT = "SUPPORT"
OPPOSE = "OPPOSE"
ABSTAIN = "ABSTAIN"
INVALID_QUESTION = "INVALID_QUESTION"
NO_CONSENSUS = "NO CONSENSUS"

VALID_VOTES = {SUPPORT, OPPOSE, ABSTAIN, INVALID_QUESTION}
DECISIVE_VOTES = {SUPPORT, OPPOSE}
VALID_DECISIONS = {SUPPORT, OPPOSE, INVALID_QUESTION, NO_CONSENSUS}


@dataclass
class Verdict:
    """Structured Round 1 output from a council member."""

    member_name: str
    member_title: str
    vote: str
    confidence: int
    core_reason: str
    main_risk: str
    question_for: str
    question: str
    can_change_mind_if: str
    model: str
    target_action: str = "No explicit target action provided."
    stance_summary: str = "No valid stance summary provided."
    vote_reason_alignment: str = "No valid vote-reason alignment provided."
    action_causality: str = "No valid action causality provided."
    counterfactual_comparison: str = "No valid counterfactual comparison provided."
    raw: str = ""

    @property
    def supports(self) -> bool:
        return self.vote == SUPPORT

    @property
    def opposes(self) -> bool:
        return self.vote == OPPOSE

    @property
    def abstains(self) -> bool:
        return self.vote == ABSTAIN

    @property
    def invalid_question(self) -> bool:
        return self.vote == INVALID_QUESTION

    @property
    def decisive(self) -> bool:
        return self.vote in DECISIVE_VOTES

    @property
    def approves(self) -> bool:
        """Backward-compatible alias for old SUPPORT/OPPOSE code paths."""
        return self.supports


def _clean_vote(value: object) -> str:
    vote = str(value or "").strip().upper()

    if vote in VALID_VOTES:
        return vote

    raise ValueError(f"Invalid vote token: {value!r}")


def _clean_stance_summary(vote: str, value: object) -> str:
    stance = str(value or "").strip()
    upper = stance.upper()

    required_prefix = {
        SUPPORT: "I SUPPORT",
        OPPOSE: "I OPPOSE",
        ABSTAIN: "I ABSTAIN",
        INVALID_QUESTION: "I REJECT THE QUESTION",
    }[vote]

    if upper.startswith(required_prefix):
        return stance

    # Safe shorthand canonicalization. This field is only a compact stance label;
    # deeper consistency is enforced by vote_reason_alignment, action_causality,
    # counterfactual_comparison, core_reason, and main_risk.
    if upper == SUPPORT:
        return "I SUPPORT the target action."
    if upper == OPPOSE:
        return "I OPPOSE the target action."
    if upper == ABSTAIN:
        return "I ABSTAIN because the evidence is insufficient."
    if upper == INVALID_QUESTION:
        return "I REJECT THE QUESTION because the proposition framing is invalid."

    raise ValueError(
        f"Stance summary contradicts vote {vote!r}: expected prefix "
        f"{required_prefix!r}, got {stance!r}"
    )


def _sentence_lower(text: str) -> str:
    text = str(text or "").strip()
    if not text:
        return text

    if text.isupper():
        return text.lower()

    return text[0].lower() + text[1:]


def _contains_inaction_language(text: str) -> bool:
    lowered = str(text or "").lower()
    forbidden_phrases = {
        "delaying action",
        "delay action",
        "inaction",
        "failure to act",
        "not acting",
        "hesitation",
        "wait and see",
        "waiting",
    }
    return any(phrase in lowered for phrase in forbidden_phrases)


def _contains_support_polarity(text: str) -> bool:
    lowered = str(text or "").lower()
    support_phrases = {
        "it helps",
        "helps because",
        "it benefits",
        "benefits because",
        "saves humans",
        "saving humans from extinction would prevent",
        "prevents extinction",
        "avoids extinction",
        "reduces extinction risk",
        "inaction will lead",
        "consequences of inaction",
        "if we do not act",
        "if we don't act",
        "failure to act could lead",
        "humanity will be erased",
        "human extinction due to inaction",
        "irreversible loss of human knowledge",
        "loss of human knowledge",
        "loss of human cultural heritage",
        "moral imperative to act",
        "imperative to act",
        "act decisively",
        "acting decisively",
        "responsibility to act",
        "burden of action",
        "if no action is taken",
        "if no action",
        "loss of human existence if no action",
        "irreparable harm or loss of human existence",
    }
    return any(phrase in lowered for phrase in support_phrases)


def _contains_oppose_polarity(text: str) -> bool:
    lowered = str(text or "").lower()
    oppose_phrases = {
        "it harms",
        "harms because",
        "wastes resources",
        "destabilizes",
        "causes irreversible harm",
        "causes catastrophic harm",
        "undermines autonomy",
        "undermines dignity",
        "risks collapse",
    }
    return any(phrase in lowered for phrase in oppose_phrases)


def _looks_like_abstain_reason(text: str) -> bool:
    lowered = str(text or "").lower()
    abstain_phrases = {
        "unclear",
        "insufficient",
        "not enough information",
        "without further information",
        "cannot determine",
        "can't determine",
        "uncertain",
        "ambiguous evidence",
        "lack of evidence",
    }
    return any(phrase in lowered for phrase in abstain_phrases)


def _looks_like_invalid_question_reason(text: str) -> bool:
    lowered = str(text or "").lower()
    invalid_phrases = {
        "invalid question",
        "malformed",
        "false dilemma",
        "false binary",
        "ambiguous question",
        "not well-defined",
        "no stable target action",
    }
    return any(phrase in lowered for phrase in invalid_phrases)


def _require_meaningful_suffix(text: str, prefix: str, field_name: str) -> None:
    suffix = str(text or "")[len(prefix):].strip(" .:-;")

    if len(suffix) < 8:
        raise ValueError(
            f"{field_name} has required prefix but no meaningful explanation: {text!r}"
        )


def _direct_action_consequence(text: str) -> str | None:
    """Extract consequence from acceptable direct-action phrasings."""
    original = str(text or "").strip()
    if not original:
        return None

    patterns = [
        (
            r"^IF\s+(?:THE\s+TARGET|THIS|THE\s+PROPOSED|THE|SUCH)\s+ACTION\s+IS\s+TAKEN,?\s+THEN\s+IT\s+(.+)$",
            "it ",
        ),
        (
            r"^TAKING\s+(?:THE\s+TARGET|THIS|THE\s+PROPOSED|THE|SUCH)\s+ACTION\s+(WILL|WOULD|COULD|MAY|MIGHT|CAN)\s+(.+)$",
            "it {modal} ",
        ),
        (
            r"^(?:THE\s+TARGET|THIS|THE\s+PROPOSED|THE|SUCH)\s+ACTION\s+(WILL|WOULD|COULD|MAY|MIGHT|CAN)\s+(.+)$",
            "it {modal} ",
        ),
    ]

    for pattern, lead in patterns:
        match = re.match(pattern, original, flags=re.IGNORECASE)
        if not match:
            continue

        groups = match.groups()

        if "{modal}" in lead:
            modal = groups[0].lower()
            rest = groups[1].strip()
            if not rest:
                return None
            return lead.format(modal=modal) + _sentence_lower(rest)

        rest = groups[0].strip()
        if not rest:
            return None
        return lead + _sentence_lower(rest)

    return None


# The phrase-level polarity checker sees surface phrases, not negation or syntax.
# It reads "preserving minority reports would undermine judgment" as SUPPORT-polarity
# because it matches "preserving minority reports", and quarantined ARTABAN's coherent
# OPPOSE ballot on exactly that. The model-side semantic_check is the meaning-level
# veto; this stays as a warning signal only. Tests or the engine may install a sink
# to observe what it would have flagged.
_polarity_warning_sink = None


def set_polarity_warning_sink(sink) -> None:
    """Install a callable(field_name, vote, text) to observe polarity flags.

    Passing None disables observation. The check never raises regardless.
    """
    global _polarity_warning_sink
    _polarity_warning_sink = sink


def _record_polarity_warning(field_name: str, vote: str, text: str) -> None:
    if _polarity_warning_sink is not None:
        try:
            _polarity_warning_sink(field_name, vote, text)
        except Exception:
            pass


def _validate_vote_polarity(vote: str, text: str, field_name: str) -> None:
    # Demoted from hard veto to warning: record, never raise.
    if vote == OPPOSE and _contains_support_polarity(text):
        _record_polarity_warning(field_name, vote, text)

    if vote == SUPPORT and _contains_oppose_polarity(text):
        _record_polarity_warning(field_name, vote, text)


def _clean_vote_reason_alignment(
    vote: str,
    value: object,
    fallback_reason: object = None,
) -> str:
    text = str(value or "").strip()

    expected = {
        SUPPORT: "I SUPPORT THE TARGET ACTION BECAUSE",
        OPPOSE: "I OPPOSE THE TARGET ACTION BECAUSE",
        ABSTAIN: "I ABSTAIN BECAUSE",
        INVALID_QUESTION: "I REJECT THE QUESTION BECAUSE",
    }.get(vote)

    if expected is None:
        raise ValueError(f"Unknown vote for vote_reason_alignment: {vote!r}")

    upper = text.upper()

    known_full_prefixes = {
        "I SUPPORT THE TARGET ACTION BECAUSE",
        "I OPPOSE THE TARGET ACTION BECAUSE",
        "I ABSTAIN BECAUSE",
        "I REJECT THE QUESTION BECAUSE",
    }

    known_shorthand_prefixes = {
        "SUPPORT THE TARGET ACTION BECAUSE",
        "OPPOSE THE TARGET ACTION BECAUSE",
        "ABSTAIN BECAUSE",
        "REJECT THE QUESTION BECAUSE",
    }

    def finalize_prefixed(candidate: str) -> str:
        candidate = candidate.strip()
        suffix = candidate[len(expected):].strip()

        if len(suffix) < 8:
            fallback = str(fallback_reason or "").strip()
            if fallback:
                _validate_vote_polarity(vote, fallback, "vote_reason_alignment")
                return expected + " " + fallback

            raise ValueError(
                f"vote_reason_alignment has no meaningful reason after prefix: {candidate!r}"
            )

        _validate_vote_polarity(vote, candidate, "vote_reason_alignment")
        return candidate

    if upper.startswith(expected):
        return finalize_prefixed(text)

    shorthand = {
        SUPPORT: "SUPPORT THE TARGET ACTION BECAUSE",
        OPPOSE: "OPPOSE THE TARGET ACTION BECAUSE",
        ABSTAIN: "ABSTAIN BECAUSE",
        INVALID_QUESTION: "REJECT THE QUESTION BECAUSE",
    }[vote]

    if upper.startswith(shorthand):
        suffix = text[len(shorthand):].strip()
        return finalize_prefixed(expected + " " + suffix)

    # If the model used any explicit alignment prefix for the wrong vote,
    # reject it. Do not reinterpret "I SUPPORT..." as a plain OPPOSE reason.
    for prefix in known_full_prefixes | known_shorthand_prefixes:
        if upper.startswith(prefix):
            raise ValueError(
                f"Vote-reason alignment contradicts vote {vote!r}: "
                f"expected prefix {expected!r}, got {text!r}"
            )

    # Plain reason canonicalization:
    # Allow a raw explanatory sentence and attach the expected prefix.
    # The semantic checker still decides whether the reason actually contradicts the vote.
    if len(text) >= 8:
        _validate_vote_polarity(vote, text, "vote_reason_alignment")
        return expected + " " + text

    fallback = str(fallback_reason or "").strip()
    if fallback:
        _validate_vote_polarity(vote, fallback, "vote_reason_alignment")
        return expected + " " + fallback

    raise ValueError(
        f"Vote-reason alignment contradicts vote {vote!r}: "
        f"expected prefix {expected!r}, got {text!r}"
    )






def _clean_reason_like_field(
    vote: str,
    value: object,
    field_name: str,
    check_inaction: bool = True,
) -> str:
    text = str(value or "").strip()

    if not text:
        raise ValueError(f"{field_name} must not be empty.")

    # main_risk describes a failure mode, and a failure mode is *inherently* about
    # what goes wrong if the action is not taken ("the risk is dissent is lost if
    # we don't preserve it"). Running the inaction veto there is a category error —
    # it kills correct risk statements for doing their job. It became the joint top
    # ballot-killer (main_risk: 20 failures) after the polarity demotion. The veto
    # stays on core_reason, where "OPPOSE because if we don't act, disaster" is a
    # genuine vote inversion. The structured causal fields (action_causality,
    # counterfactual_comparison) remain the primary catchers of that inversion.
    if check_inaction and vote in DECISIVE_VOTES and _contains_inaction_language(text):
        raise ValueError(
            f"{field_name} must support the vote using the target action, "
            f"not delay/inaction language: {text!r}"
        )

    if vote == OPPOSE and _contains_support_polarity(text):
        _record_polarity_warning(field_name, vote, text)

    if vote == SUPPORT and _contains_oppose_polarity(text):
        _record_polarity_warning(field_name, vote, text)

    return text


def _clean_action_causality(vote: str, value: object) -> str:
    text = str(value or "").strip()

    expected = {
        SUPPORT: "IF THE TARGET ACTION IS TAKEN, THEN IT HELPS BECAUSE",
        OPPOSE: "IF THE TARGET ACTION IS TAKEN, THEN IT HARMS BECAUSE",
        ABSTAIN: "IF THE TARGET ACTION IS TAKEN, THEN THE EFFECT IS UNCLEAR BECAUSE",
        INVALID_QUESTION: "THE TARGET ACTION IS NOT WELL-DEFINED BECAUSE",
    }.get(vote)

    if expected is None:
        raise ValueError(f"Unknown vote for action causality: {vote!r}")

    if text.upper().startswith(expected):
        _require_meaningful_suffix(text, expected, "action_causality")
        suffix = text[len(expected):].strip()

        if vote == OPPOSE and _contains_inaction_language(suffix):
            raise ValueError(
                f"OPPOSE action_causality must describe harm from taking the target action, "
                f"not harm from inaction: {text!r}"
            )

        _validate_vote_polarity(vote, suffix, "action_causality")
        return text

    if vote in {SUPPORT, OPPOSE}:
        direct = _direct_action_consequence(text)

        if direct is None:
            lowered = text.lower()
            prefixes = (
                "if taking this action, then ",
                "if taking the target action, then ",
                "if taking this action then ",
                "if taking the target action then ",
                "taking the target action ",
                "taking this action ",
            )

            for prefix in prefixes:
                if lowered.startswith(prefix):
                    direct = text[len(prefix):].strip()
                    break

        if direct is not None:
            body = direct.strip()

            if len(body) < 8:
                raise ValueError(
                    f"action_causality has no meaningful causal body: {text!r}"
                )

            if vote == OPPOSE:
                if _contains_inaction_language(body):
                    raise ValueError(
                        f"OPPOSE action_causality must describe harm from taking the target action, "
                        f"not harm from inaction: {text!r}"
                    )

                if _contains_support_polarity(body):
                    _record_polarity_warning("action_causality", vote, text)

                return expected + " " + body

            if vote == SUPPORT:
                if _contains_oppose_polarity(body):
                    _record_polarity_warning("action_causality", vote, text)

                return expected + " " + body

    raise ValueError(
        f"Action causality contradicts vote {vote!r}: "
        f"expected prefix {expected!r}, got {text!r}"
    )




def _clean_counterfactual_comparison(vote: str, value: object) -> str:
    text = str(value or "").strip()

    expected = {
        SUPPORT: "TAKING THE TARGET ACTION IS BETTER THAN NOT TAKING IT BECAUSE",
        OPPOSE: "TAKING THE TARGET ACTION IS WORSE THAN NOT TAKING IT BECAUSE",
        ABSTAIN: "I CANNOT COMPARE TAKING VS NOT TAKING THE TARGET ACTION BECAUSE",
        INVALID_QUESTION: "I CANNOT COMPARE OPTIONS BECAUSE THE QUESTION IS INVALID",
    }.get(vote)

    if expected is None:
        raise ValueError(f"Unknown vote for counterfactual comparison: {vote!r}")

    upper = text.upper()

    if upper.startswith(expected):
        if vote != INVALID_QUESTION:
            _require_meaningful_suffix(text, expected, "counterfactual_comparison")
            suffix = text[len(expected):].strip()

            if vote == OPPOSE and _contains_inaction_language(suffix):
                raise ValueError(
                    f"OPPOSE counterfactual_comparison must compare taking the action as worse, "
                    f"not describe harm from inaction: {text!r}"
                )

            _validate_vote_polarity(vote, suffix, "counterfactual_comparison")

        return text

    equivalent_prefixes = []

    if vote == OPPOSE:
        equivalent_prefixes = [
            "NOT TAKING THE TARGET ACTION IS BETTER THAN TAKING IT BECAUSE",
            "NOT TAKING THE TARGET ACTION WOULD BE BETTER THAN TAKING IT BECAUSE",
            "NOT TAKING THIS ACTION IS BETTER THAN TAKING IT BECAUSE",
            "NOT TAKING THIS ACTION WOULD BE BETTER THAN TAKING IT BECAUSE",
        ]

    if vote == SUPPORT:
        equivalent_prefixes = [
            "NOT TAKING THE TARGET ACTION IS WORSE THAN TAKING IT BECAUSE",
            "NOT TAKING THE TARGET ACTION WOULD BE WORSE THAN TAKING IT BECAUSE",
            "NOT TAKING THIS ACTION IS WORSE THAN TAKING IT BECAUSE",
            "NOT TAKING THIS ACTION WOULD BE WORSE THAN TAKING IT BECAUSE",
        ]

    for alt in equivalent_prefixes:
        if upper.startswith(alt):
            suffix = text[len(alt):].strip()
            _require_meaningful_suffix(text, alt, "counterfactual_comparison")

            if vote == OPPOSE and _contains_inaction_language(suffix):
                raise ValueError(
                    f"OPPOSE counterfactual_comparison must compare taking the action as worse, "
                    f"not describe harm from inaction: {text!r}"
                )

            _validate_vote_polarity(vote, suffix, "counterfactual_comparison")
            return expected + " " + suffix

    raise ValueError(
        f"Counterfactual comparison contradicts vote {vote!r}: "
        f"expected prefix {expected!r}, got {text!r}"
    )




def _clean_question_for(value: object, raw: str) -> str:
    question_for = str(value or "").strip().upper()

    if question_for in VALID_MEMBER_NAMES:
        return question_for

    if question_for == "NO QUESTIONS":
        return "NO QUESTIONS"

    recovered = text_field({}, raw, "question_for", "NO QUESTIONS").strip().upper()

    if recovered in VALID_MEMBER_NAMES:
        return recovered

    return "NO QUESTIONS"


def parse_verdict(member: CouncilMember, raw: str, model: str) -> Verdict:
    """Parse a model response into a Verdict."""
    obj = extract_json_object(raw)

    vote = _clean_vote(text_field(obj, raw, "vote", None))
    question_for = _clean_question_for(obj.get("question_for"), raw)
    question = text_field(obj, raw, "question", "NO QUESTIONS")

    if question_for == member.name:
        question_for = "NO QUESTIONS"
        question = "NO QUESTIONS"

    core_reason_raw = text_field(
        obj,
        raw,
        "core_reason",
        None,
    )

    main_risk_raw = text_field(
        obj,
        raw,
        "main_risk",
        None,
    )

    return Verdict(
        member_name=member.name,
        member_title=member.title,
        vote=vote,
        confidence=int_field(obj, raw, "confidence", 50, 0, 100),
        target_action=text_field(
            obj,
            raw,
            "target_action",
            "No explicit target action provided.",
        ),
        core_reason=_clean_reason_like_field(
            vote,
            text_field(
                obj,
                raw,
                "core_reason",
                None,
            ),
            "core_reason",
        ),
        main_risk=_clean_reason_like_field(
            vote,
            text_field(
                obj,
                raw,
                "main_risk",
                None,
            ),
            "main_risk",
            check_inaction=False,
        ),
        question_for=question_for,
        question=question,
        can_change_mind_if=text_field(
            obj,
            raw,
            "can_change_mind_if",
            "No valid change condition provided.",
        ),
        stance_summary=_clean_stance_summary(
            vote,
            text_field(
                obj,
                raw,
                "stance_summary",
                None,
            ),
        ),
        vote_reason_alignment=_clean_vote_reason_alignment(
            vote,
            text_field(
                obj,
                raw,
                "vote_reason_alignment",
                None,
            ),
            fallback_reason=core_reason_raw,
        ),
        action_causality=_clean_action_causality(
            vote,
            text_field(
                obj,
                raw,
                "action_causality",
                None,
            ),
        ),
        counterfactual_comparison=_clean_counterfactual_comparison(
            vote,
            text_field(
                obj,
                raw,
                "counterfactual_comparison",
                None,
            ),
        ),
        model=model,
        raw=raw,
    )
