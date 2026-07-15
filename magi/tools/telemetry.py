"""Quarantine telemetry: count WHY ballots are rejected.

The independence probe told us that a large share of ballots never reach the
tally — they are rejected by validation and quarantined as ABSTAIN 0%. It could
not tell us what killed them, so any fix would be a guess.

This module classifies each validation failure into (field, kind) and counts
them, so the probe can report the real distribution:

    action_causality / prefix_mismatch ......... 41
    vote_reason_alignment / polarity_blocklist .. 12

Then the top offender gets fixed and the abstain rate is measured again. Same
discipline as the vote-ordering fix: measure the cause, change one thing, remeasure.

Counters are process-global because the council runs members in a thread pool;
all mutation is under a lock. Pure stdlib, no third-party dependencies.
"""

from __future__ import annotations

import threading
from collections import Counter
from dataclasses import dataclass, field

_LOCK = threading.Lock()

_failures: Counter = Counter()  # every validation failure, including repaired ones
_quarantines: Counter = Counter()  # only the failure that finally killed a ballot
_failures_by_member: Counter = Counter()
_quarantines_by_member: Counter = Counter()
_repairs: Counter = Counter()  # "attempted" / "succeeded"

# Field names as they appear in validator messages, longest/most specific first
# so that "action_causality" is not shadowed by a looser match.
_FIELD_TOKENS = (
    ("counterfactual_comparison", "counterfactual_comparison"),
    ("counterfactual comparison", "counterfactual_comparison"),
    ("action_causality", "action_causality"),
    ("action causality", "action_causality"),
    ("vote_reason_alignment", "vote_reason_alignment"),
    ("vote-reason alignment", "vote_reason_alignment"),
    ("stance_summary", "stance_summary"),
    ("stance summary", "stance_summary"),
    ("core_reason", "core_reason"),
    ("main_risk", "main_risk"),
    ("target_action", "target_action"),
    ("vote token", "vote"),
)


def classify(error: object) -> tuple[str, str]:
    """Map a validation error message to (field, kind).

    kind explains the mechanism of rejection, which is what tells us whether the
    validator is catching real inversions or eating valid ballots:

    - polarity_blocklist : hit a hardcoded phrase list (suspect false positives)
    - prefix_mismatch    : required incantation absent or wrong
    - prefix_empty       : incantation present but no real clause after it
    - inaction_language  : reason argued from not-acting instead of acting
    - reasoning_inverted : the model-side semantic check disagreed with the vote
    - invalid_vote_token : vote field itself unparseable
    - empty_field        : field blank
    """
    low = str(error).lower()

    if "semantic vote check contradicted" in low:
        return ("semantic_check", "reasoning_inverted")

    if "-polarity language" in low:
        kind = "polarity_blocklist"
    elif "inaction" in low:
        kind = "inaction_language"
    elif "expected prefix" in low or "contradicts vote" in low:
        kind = "prefix_mismatch"
    elif "no meaningful" in low:
        kind = "prefix_empty"
    elif "must not be empty" in low:
        kind = "empty_field"
    elif "invalid vote token" in low or "unknown vote for" in low:
        kind = "invalid_vote_token"
    else:
        kind = "other"

    for token, name in _FIELD_TOKENS:
        if token in low:
            return (name, kind)

    return ("other", kind)


def reset() -> None:
    """Clear all counters. Call before a measured run."""
    with _LOCK:
        _failures.clear()
        _quarantines.clear()
        _failures_by_member.clear()
        _quarantines_by_member.clear()
        _repairs.clear()


def record_failure(member_name: str, error: object) -> None:
    """A ballot failed validation. It may still be repaired."""
    key = classify(error)
    with _LOCK:
        _failures[key] += 1
        _failures_by_member[member_name] += 1


def record_repair_attempt(member_name: str) -> None:
    with _LOCK:
        _repairs["attempted"] += 1


def record_repair_success(member_name: str) -> None:
    """A ballot failed at least once, then passed after repair."""
    with _LOCK:
        _repairs["succeeded"] += 1


def record_quarantine(member_name: str, error: object) -> None:
    """A ballot died after every repair attempt and became ABSTAIN 0%."""
    key = classify(error)
    with _LOCK:
        _quarantines[key] += 1
        _quarantines_by_member[member_name] += 1


@dataclass
class TelemetrySnapshot:
    failures: Counter = field(default_factory=Counter)
    quarantines: Counter = field(default_factory=Counter)
    failures_by_member: Counter = field(default_factory=Counter)
    quarantines_by_member: Counter = field(default_factory=Counter)
    repairs: Counter = field(default_factory=Counter)

    @property
    def total_failures(self) -> int:
        return sum(self.failures.values())

    @property
    def total_quarantines(self) -> int:
        return sum(self.quarantines.values())

    @property
    def repair_success_rate(self) -> float:
        attempted = self.repairs.get("attempted", 0)
        if not attempted:
            return 0.0
        return self.repairs.get("succeeded", 0) / attempted

    def top_causes(self, n: int = 8) -> list[tuple[tuple[str, str], int]]:
        return self.failures.most_common(n)

    def top_killers(self, n: int = 8) -> list[tuple[tuple[str, str], int]]:
        """The failures that actually ended a ballot's life."""
        return self.quarantines.most_common(n)


def snapshot() -> TelemetrySnapshot:
    with _LOCK:
        return TelemetrySnapshot(
            failures=Counter(_failures),
            quarantines=Counter(_quarantines),
            failures_by_member=Counter(_failures_by_member),
            quarantines_by_member=Counter(_quarantines_by_member),
            repairs=Counter(_repairs),
        )
