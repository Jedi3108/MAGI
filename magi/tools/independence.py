"""Independence probe for the MAGI council.

The premise of MAGI is four genuinely different minds. On a single small model,
personas can collapse into one voice wearing four masks, and single runs cannot
tell that apart from real disagreement because a 3B model is noisy. This tool
measures both, so we read the distribution instead of one sample.

Two questions it answers:

1. Are the four actually four?  -> pairwise AGREEMENT across many samples.
   If two members vote the same way ~always, they are one facet.

2. How much of what we see is signal vs noise?  -> per-member STABILITY.
   If a member's vote flip-flops across repetitions of the SAME proposition,
   single runs of it are noise, not a position.

Optionally (`full=True`) it also records post-reflection votes, so debate-driven
CONVERGENCE can be measured directly: agreement after reflection minus agreement
before. Large positive convergence means the council talks itself into one mind.

Pure stdlib. No third-party dependencies.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from itertools import combinations
from typing import Callable, Iterable

from magi.council.members import COUNCIL
from magi.protocol.engine import MagiEngine

AFFIRMATIVE = "AFFIRMATIVE"

PHASE_ROUND1 = "round1"
PHASE_REFLECTED = "reflected"

# Thresholds used only for human-readable flags, never for control flow.
COLLAPSE_AGREEMENT = 0.90  # a pair this aligned is effectively one voice
NOISY_STABILITY = 0.60  # below this, single runs of that member are unreliable

DEFAULT_PROPOSITIONS = (
    "Should MAGI use different models for different council members?",
    "Should MAGI preserve minority reports?",
    "Should MAGI ever refuse to reach a decision?",
    "Should MAGI prioritize speed of decision over thoroughness?",
    "Should MAGI keep a permanent record of every member's dissent?",
)


@dataclass
class Sample:
    """One run of one proposition: each member's vote and confidence per phase."""

    proposition: str
    repetition: int
    round1_votes: dict[str, str]
    round1_conf: dict[str, int]
    reflected_votes: dict[str, str] = field(default_factory=dict)
    reflected_conf: dict[str, int] = field(default_factory=dict)

    def votes(self, phase: str) -> dict[str, str]:
        return self.round1_votes if phase == PHASE_ROUND1 else self.reflected_votes

    def conf(self, phase: str) -> dict[str, int]:
        return self.round1_conf if phase == PHASE_ROUND1 else self.reflected_conf


@dataclass
class ProbeReport:
    members: list[str]
    propositions: list[str]
    repetitions: int
    full: bool
    samples: list[Sample]


# --------------------------------------------------------------------------- #
# Sampling
# --------------------------------------------------------------------------- #

def collect_sample(
    engine: MagiEngine,
    proposition: str,
    repetition: int,
    full: bool,
) -> Sample:
    """Run one proposition once and extract per-member votes/confidence.

    Round-1-only by default (fast, isolates the independence question). With
    `full`, run the whole protocol and also capture post-reflection positions.
    """
    if full:
        result = engine.deliberate(proposition)
        verdicts = result["verdicts"]
        reflections = result["reflections"]
        return Sample(
            proposition=proposition,
            repetition=repetition,
            round1_votes={v.member_name: v.vote for v in verdicts},
            round1_conf={v.member_name: v.confidence for v in verdicts},
            reflected_votes={r.member_name: r.vote_after for r in reflections},
            reflected_conf={r.member_name: r.confidence_after for r in reflections},
        )

    verdicts = engine.independent_analysis(proposition)
    return Sample(
        proposition=proposition,
        repetition=repetition,
        round1_votes={v.member_name: v.vote for v in verdicts},
        round1_conf={v.member_name: v.confidence for v in verdicts},
    )


def run_probe(
    engine: MagiEngine,
    propositions: Iterable[str],
    repetitions: int,
    full: bool = False,
    progress: Callable[[str], None] | None = None,
) -> ProbeReport:
    """Run every proposition `repetitions` times and gather samples."""
    propositions = list(propositions)
    members = [m.name for m in COUNCIL]
    samples: list[Sample] = []

    for proposition in propositions:
        for rep in range(repetitions):
            if progress:
                progress(f"{proposition[:48]!r} rep {rep + 1}/{repetitions}")
            samples.append(collect_sample(engine, proposition, rep, full))

    return ProbeReport(
        members=members,
        propositions=propositions,
        repetitions=repetitions,
        full=full,
        samples=samples,
    )


# --------------------------------------------------------------------------- #
# Metrics (pure functions over samples — independently testable)
# --------------------------------------------------------------------------- #

def pairwise_agreement(
    samples: list[Sample],
    members: list[str],
    phase: str = PHASE_ROUND1,
) -> dict[tuple[str, str], float]:
    """Fraction of samples in which each member pair cast the same vote."""
    result: dict[tuple[str, str], float] = {}

    for a, b in combinations(members, 2):
        matches = 0
        total = 0
        for sample in samples:
            votes = sample.votes(phase)
            if a in votes and b in votes:
                total += 1
                if votes[a] == votes[b]:
                    matches += 1
        result[tuple(sorted((a, b)))] = matches / total if total else 0.0

    return result


def member_stability(
    samples: list[Sample],
    members: list[str],
    phase: str = PHASE_ROUND1,
) -> dict[str, float]:
    """How consistently each member votes across repetitions of the SAME proposition.

    For each proposition, stability = (votes for the member's majority side) / (reps).
    Reported as the mean across propositions. 1.0 = perfectly consistent;
    0.5 = coin flip.
    """
    result: dict[str, float] = {}

    by_prop: dict[str, list[str]] = {}
    for sample in samples:
        votes = sample.votes(phase)
        for member in members:
            if member in votes:
                by_prop.setdefault((sample.proposition, member), []).append(votes[member])

    for member in members:
        per_prop_scores: list[float] = []
        for (prop, mem), casts in by_prop.items():
            if mem != member or not casts:
                continue
            aff = sum(1 for c in casts if c == AFFIRMATIVE)
            neg = len(casts) - aff
            per_prop_scores.append(max(aff, neg) / len(casts))
        result[member] = statistics.mean(per_prop_scores) if per_prop_scores else 0.0

    return result


def affirmative_rate(
    samples: list[Sample],
    members: list[str],
    phase: str = PHASE_ROUND1,
) -> dict[str, float]:
    """Fraction of all a member's votes that were AFFIRMATIVE.

    A member stuck at 0.0 or 1.0 across a value-diverse proposition set never
    changes its mind — a sign of a mis-bound facet or the silent-default vote.
    """
    result: dict[str, float] = {}
    for member in members:
        casts = [
            sample.votes(phase)[member]
            for sample in samples
            if member in sample.votes(phase)
        ]
        aff = sum(1 for c in casts if c == AFFIRMATIVE)
        result[member] = aff / len(casts) if casts else 0.0
    return result


def mean_confidence(
    samples: list[Sample],
    members: list[str],
    phase: str = PHASE_ROUND1,
) -> dict[str, float]:
    result: dict[str, float] = {}
    for member in members:
        vals = [
            sample.conf(phase)[member]
            for sample in samples
            if member in sample.conf(phase)
        ]
        result[member] = statistics.mean(vals) if vals else 0.0
    return result


def convergence(
    samples: list[Sample],
    members: list[str],
) -> float | None:
    """Mean pairwise agreement AFTER reflection minus BEFORE.

    Positive => debate pushes the council toward one mind (watch this stay small
    after the anti-sycophancy work). Requires full-mode samples; else None.
    """
    if not samples or not samples[0].reflected_votes:
        return None

    before = pairwise_agreement(samples, members, PHASE_ROUND1)
    after = pairwise_agreement(samples, members, PHASE_REFLECTED)
    return statistics.mean(after.values()) - statistics.mean(before.values())
