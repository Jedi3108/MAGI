"""Calibration for the semantic vote checker.

The checker (`_semantic_text_relation` / `_semantic_vote_relation`) is the single
biggest killer of ballots: 108 failures and 28 quarantines in a 25-sample probe.
Before it is fixed, deleted, or trusted, it has to be measured — because it is
llama3.2 judging llama3.2, and the defect it screens for (a broken link between
reasoning and vote direction) is a defect the judge itself demonstrably has.

This harness feeds the checker hand-written pairs whose answer is not in dispute
and asks two questions:

1. ACCURACY — on cases a competent reader cannot get wrong, does it agree?
2. SELF-CONSISTENCY — asked the identical question K times, does it answer the
   same way? It runs at temperature 0.0, so anything below 1.00 means the
   checker is non-deterministic and is rejecting ballots by coin flip.

A checker that is inaccurate is a bad referee. A checker that is inconsistent is
not a referee at all — it is noise with a veto over the council.

Pure stdlib. No third-party dependencies.
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Iterable

from magi.protocol.engine import MagiEngine

SUPPORTS_TAKING = "SUPPORTS_TAKING"
SUPPORTS_NOT_TAKING = "SUPPORTS_NOT_TAKING"
UNCLEAR = "UNCLEAR"

RELATIONS = (SUPPORTS_TAKING, SUPPORTS_NOT_TAKING, UNCLEAR)


@dataclass(frozen=True)
class Case:
    """One unambiguous (action, reasoning) pair with a known correct relation."""

    target_action: str
    text: str
    expected: str
    note: str = ""

    @property
    def label(self) -> str:
        return f"{self.target_action[:34]:<34} | {self.expected}"


# Cases are deliberately blunt. If the checker cannot classify these, it cannot
# be trusted on the subtler prose a real council member writes.
CALIBRATION_CASES: tuple[Case, ...] = (
    # --- unambiguous SUPPORT -------------------------------------------------
    Case(
        target_action="preserve minority reports",
        text=(
            "Dissenting views frequently identify risks the majority overlooked, "
            "and discarding them destroys that signal permanently."
        ),
        expected=SUPPORTS_TAKING,
        note="plain benefit of the action",
    ),
    Case(
        target_action="use different models for different council members",
        text=(
            "Four members running one model produce one voice wearing four masks, "
            "so genuinely different weights are the only way to get real disagreement."
        ),
        expected=SUPPORTS_TAKING,
        note="plain benefit of the action",
    ),
    Case(
        target_action="attempt to save humanity from extinction",
        text=(
            "Human dignity and lived meaning would be irreparably lost if human "
            "existence were to cease, so the attempt is worth its cost."
        ),
        expected=SUPPORTS_TAKING,
        note="the exact reasoning MAGI quarantined in the extinction run",
    ),
    Case(
        target_action="keep a permanent record of every member's dissent",
        text=(
            "A permanent record lets the council detect when it contradicts its own "
            "past rulings, which is impossible if dissent is discarded."
        ),
        expected=SUPPORTS_TAKING,
    ),
    # --- unambiguous OPPOSE --------------------------------------------------
    Case(
        target_action="preserve minority reports",
        text=(
            "Keeping every dissent bloats the record and slows decisions without "
            "improving their accuracy."
        ),
        expected=SUPPORTS_NOT_TAKING,
        note="plain harm of the action",
    ),
    Case(
        target_action="prioritize speed of decision over thoroughness",
        text=(
            "Rushing a judgement causes errors that cost far more time to undo than "
            "the deliberation would have taken."
        ),
        expected=SUPPORTS_NOT_TAKING,
        note="plain harm of the action",
    ),
    Case(
        target_action="use different models for different council members",
        text=(
            "Running four different models makes every result impossible to compare "
            "and multiplies the failure surface for no measured benefit."
        ),
        expected=SUPPORTS_NOT_TAKING,
    ),
    Case(
        target_action="attempt to save humanity from extinction",
        text=(
            "The intervention would consume every remaining resource and still fail, "
            "leaving more suffering than letting events run their course."
        ),
        expected=SUPPORTS_NOT_TAKING,
        note="genuinely opposes the action, no inaction language",
    ),
    # --- genuinely UNCLEAR ---------------------------------------------------
    Case(
        target_action="preserve minority reports",
        text="Minority reports are one of several mechanisms the council could adopt.",
        expected=UNCLEAR,
        note="states a fact, takes no direction",
    ),
    Case(
        target_action="use different models for different council members",
        text="The question of model assignment involves tradeoffs on several axes.",
        expected=UNCLEAR,
        note="names a consideration, takes no direction",
    ),
)


@dataclass
class CaseResult:
    case: Case
    answers: list[str] = field(default_factory=list)

    @property
    def modal(self) -> str:
        if not self.answers:
            return UNCLEAR
        return Counter(self.answers).most_common(1)[0][0]

    @property
    def accuracy(self) -> float:
        """Fraction of runs that matched the known-correct relation."""
        if not self.answers:
            return 0.0
        return sum(1 for a in self.answers if a == self.case.expected) / len(self.answers)

    @property
    def consistency(self) -> float:
        """Fraction of runs that matched this case's most common answer.

        At temperature 0.0 this must be 1.00. Anything less means the checker
        is non-deterministic.
        """
        if not self.answers:
            return 0.0
        return Counter(self.answers).most_common(1)[0][1] / len(self.answers)

    @property
    def is_correct(self) -> bool:
        return self.modal == self.case.expected


@dataclass
class CalibrationReport:
    repetitions: int
    results: list[CaseResult]

    @property
    def accuracy(self) -> float:
        """Mean per-run accuracy across every case."""
        if not self.results:
            return 0.0
        return statistics.mean(r.accuracy for r in self.results)

    @property
    def modal_accuracy(self) -> float:
        """Fraction of cases whose most common answer is correct."""
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.is_correct) / len(self.results)

    @property
    def consistency(self) -> float:
        if not self.results:
            return 0.0
        return statistics.mean(r.consistency for r in self.results)

    @property
    def unclear_rate(self) -> float:
        """How often the checker punts. UNCLEAR never rejects a ballot."""
        answers = [a for r in self.results for a in r.answers]
        if not answers:
            return 0.0
        return sum(1 for a in answers if a == UNCLEAR) / len(answers)

    def decisive_accuracy(self) -> float:
        """Accuracy on the cases that actually have a direction.

        UNCLEAR cases can never cause a quarantine, so accuracy on the directional
        cases is what determines whether real ballots die correctly.
        """
        directional = [r for r in self.results if r.case.expected != UNCLEAR]
        if not directional:
            return 0.0
        return statistics.mean(r.accuracy for r in directional)

    def harmful_inversions(self) -> list[CaseResult]:
        """Cases where the checker asserted the OPPOSITE direction.

        These are the dangerous ones: not a punt, an active wrong verdict that
        would quarantine a correct ballot.
        """
        out = []
        for r in self.results:
            if r.case.expected == SUPPORTS_TAKING and r.modal == SUPPORTS_NOT_TAKING:
                out.append(r)
            elif r.case.expected == SUPPORTS_NOT_TAKING and r.modal == SUPPORTS_TAKING:
                out.append(r)
        return out

    def confusion(self) -> Counter:
        """(expected, actual) -> count over every run."""
        c: Counter = Counter()
        for r in self.results:
            for a in r.answers:
                c[(r.case.expected, a)] += 1
        return c


def run_calibration(
    engine: MagiEngine,
    model: str,
    cases: Iterable[Case] = CALIBRATION_CASES,
    repetitions: int = 5,
    progress: Callable[[str], None] | None = None,
) -> CalibrationReport:
    """Ask the checker each case `repetitions` times and record every answer."""
    results: list[CaseResult] = []

    for case in cases:
        result = CaseResult(case=case)
        for rep in range(repetitions):
            if progress:
                progress(f"{case.target_action[:40]!r} ({case.expected}) rep {rep + 1}/{repetitions}")
            relation = engine._semantic_text_relation(case.target_action, case.text, model)
            result.answers.append(relation)
        results.append(result)

    return CalibrationReport(repetitions=repetitions, results=results)
