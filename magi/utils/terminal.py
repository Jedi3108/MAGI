"""Terminal rendering utilities for MAGI."""

from __future__ import annotations

from magi.chair.dossier import DecisionDossier
from magi.council.verdict import Verdict
from magi.protocol.examination import CrossExaminationAnswer, SatisfactionEvaluation
from magi.protocol.reflection import Reflection


class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    AMBER = "\033[38;5;214m"
    RED = "\033[38;5;196m"
    GREEN = "\033[38;5;46m"
    CYAN = "\033[38;5;51m"
    GREY = "\033[38;5;244m"
    MAGENTA = "\033[38;5;201m"


COLORS = {
    "MELCHIOR": C.CYAN,
    "BALTHASAR": C.GREEN,
    "CASPER": C.MAGENTA,
    "ARTABAN": C.AMBER,
}


def confidence_bar(confidence: int, width: int = 12) -> str:
    filled = round(confidence / 100 * width)
    return f"{C.AMBER}{'█' * filled}{C.GREY}{'░' * (width - filled)}{C.RESET}"


def render_banner() -> None:
    print(
        f"""{C.AMBER}{C.BOLD}
MAGI
A Local Deliberative Intelligence Architecture
{C.RESET}{C.GREY}MELCHIOR · BALTHASAR · CASPER · ARTABAN{C.RESET}
"""
    )


def render_verdicts(verdicts: list[Verdict]) -> None:
    print(f"\n{C.GREY}{'─' * 72}{C.RESET}")
    print(f"{C.BOLD}ROUND 1 :: INDEPENDENT ANALYSIS{C.RESET}")
    print(f"{C.GREY}{'─' * 72}{C.RESET}")

    for verdict in verdicts:
        color = COLORS.get(verdict.member_name, C.GREY)
        vote_color = C.GREEN if verdict.approves else C.RED
        bar = confidence_bar(verdict.confidence)

        print(
            f"\n{color}{C.BOLD}{verdict.member_name:<10}{C.RESET} "
            f"{C.DIM}{verdict.member_title:<14}{C.RESET} "
            f"{vote_color}{verdict.vote:<11}{C.RESET} "
            f"{bar} {verdict.confidence:>3}% "
            f"{C.GREY}{verdict.model}{C.RESET}"
        )
        print(f"  Reason: {verdict.core_reason}")
        print(f"  Risk:   {verdict.main_risk}")
        print(f"  Asks:   {verdict.question_for} — {verdict.question}")
        print(f"  Would change mind if: {verdict.can_change_mind_if}")


def render_cross_examination(answers: list[CrossExaminationAnswer]) -> None:
    print(f"\n{C.GREY}{'─' * 72}{C.RESET}")
    print(f"{C.BOLD}ROUND 2 :: CROSS-EXAMINATION{C.RESET}")
    print(f"{C.GREY}{'─' * 72}{C.RESET}")

    if not answers:
        print(f"{C.GREY}No routed questions. Cross-examination skipped.{C.RESET}")
        return

    for answer in answers:
        asker_color = COLORS.get(answer.asker_name, C.GREY)
        target_color = COLORS.get(answer.target_name, C.GREY)

        print(
            f"\n{asker_color}{C.BOLD}{answer.asker_name}{C.RESET} "
            f"{C.GREY}asks{C.RESET} "
            f"{target_color}{C.BOLD}{answer.target_name}{C.RESET}"
        )
        print(f"  Q: {answer.question}")
        print(f"  A: {answer.answer}")
        print(f"  {C.GREY}model: {answer.model}{C.RESET}")


def render_satisfaction_evaluations(evaluations: list[SatisfactionEvaluation]) -> None:
    print(f"\n{C.GREY}{'─' * 72}{C.RESET}")
    print(f"{C.BOLD}ROUND 3 :: SATISFACTION EVALUATION{C.RESET}")
    print(f"{C.GREY}{'─' * 72}{C.RESET}")

    if not evaluations:
        print(f"{C.GREY}No answers to evaluate. Satisfaction evaluation skipped.{C.RESET}")
        return

    for evaluation in evaluations:
        asker_color = COLORS.get(evaluation.asker_name, C.GREY)
        target_color = COLORS.get(evaluation.target_name, C.GREY)

        if evaluation.satisfaction == "SATISFIED":
            status_color = C.GREEN
        elif evaluation.satisfaction == "NOT SATISFIED":
            status_color = C.RED
        else:
            status_color = C.AMBER

        print(
            f"\n{asker_color}{C.BOLD}{evaluation.asker_name}{C.RESET} "
            f"{C.GREY}evaluates answer from{C.RESET} "
            f"{target_color}{C.BOLD}{evaluation.target_name}{C.RESET}"
        )
        print(f"  Status: {status_color}{evaluation.satisfaction}{C.RESET}")
        print(f"  Reason: {evaluation.reason}")
        print(f"  Confidence delta: {evaluation.confidence_delta:+d}")
        print(f"  {C.GREY}model: {evaluation.model}{C.RESET}")


def render_reflections(reflections: list[Reflection]) -> None:
    print(f"\n{C.GREY}{'─' * 72}{C.RESET}")
    print(f"{C.BOLD}ROUND 4 :: REFLECTION{C.RESET}")
    print(f"{C.GREY}{'─' * 72}{C.RESET}")

    for reflection in reflections:
        color = COLORS.get(reflection.member_name, C.GREY)
        vote_color = C.GREEN if reflection.approves else C.RED

        print(
            f"\n{color}{C.BOLD}{reflection.member_name:<10}{C.RESET} "
            f"{C.DIM}{reflection.member_title:<14}{C.RESET} "
            f"{vote_color}{reflection.vote_before} → {reflection.vote_after}{C.RESET}"
        )
        print(
            f"  Confidence: {reflection.confidence_before} → "
            f"{reflection.confidence_after}"
        )
        print(f"  Learned: {reflection.learned}")
        print(f"  Reason:  {reflection.reason}")
        print(f"  {C.GREY}model: {reflection.model}{C.RESET}")


def render_decision(decision: dict) -> None:
    result = decision["decision"]

    if result == "AFFIRMATIVE":
        color = C.GREEN
    elif result == "NEGATIVE":
        color = C.RED
    else:
        color = C.AMBER

    print(f"\n{color}{'═' * 72}{C.RESET}")
    print(f"{color}{C.BOLD}MAGI DECISION AFTER REFLECTION :: {result}{C.RESET}")
    print(
        f"{color}Split: {decision['affirmative']} affirmative / "
        f"{decision['negative']} negative{C.RESET}"
    )
    print(f"{color}{'═' * 72}{C.RESET}\n")


def render_dossier(dossier: DecisionDossier) -> None:
    print(f"\n{C.AMBER}{'═' * 72}{C.RESET}")
    print(f"{C.AMBER}{C.BOLD}CHAIR DOSSIER :: NON-VOTING SUMMARY{C.RESET}")
    print(f"{C.AMBER}{'═' * 72}{C.RESET}")

    print(f"\n{C.BOLD}Decision:{C.RESET} {dossier.decision}")
    print(f"{C.BOLD}Vote split:{C.RESET} {dossier.vote_split}")

    print(f"\n{C.BOLD}Majority reasoning:{C.RESET}")
    print(f"  {dossier.majority_reasoning}")

    print(f"\n{C.BOLD}Minority reasoning:{C.RESET}")
    print(f"  {dossier.minority_reasoning}")

    print(f"\n{C.BOLD}Key risks:{C.RESET}")
    print(f"  {dossier.key_risks}")

    print(f"\n{C.BOLD}Outstanding uncertainties:{C.RESET}")
    print(f"  {dossier.outstanding_uncertainties}")

    print(f"\n{C.BOLD}Required conditions:{C.RESET}")
    print(f"  {dossier.required_conditions}")

    print(f"\n{C.BOLD}Recommended next action:{C.RESET}")
    print(f"  {dossier.recommended_next_action}")

    print(f"\n{C.GREY}chair model: {dossier.model}{C.RESET}")
    print(f"{C.AMBER}{'═' * 72}{C.RESET}\n")
