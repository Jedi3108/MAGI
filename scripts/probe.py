#!/usr/bin/env python3
"""Independence probe CLI for MAGI.

Measures whether the council is genuinely four minds or one voice in four masks,
and how much of a single run is signal vs 3B noise.

Examples:
  python scripts/probe.py --mock -k 5
  python scripts/probe.py --model llama3.2 -k 5
  python scripts/probe.py --model llama3.2 -k 5 --full
  python scripts/probe.py --model llama3.2 -k 3 "Should MAGI self-terminate on compromise?"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from magi.models.ollama import OllamaError
from magi.protocol.engine import MagiEngine
from magi.tools.independence import (
    COLLAPSE_AGREEMENT,
    DEFAULT_PROPOSITIONS,
    NOISY_STABILITY,
    PHASE_REFLECTED,
    PHASE_ROUND1,
    ProbeReport,
    affirmative_rate,
    convergence,
    mean_confidence,
    member_stability,
    pairwise_agreement,
    run_probe,
)
from magi.utils.terminal import C

ABBREV = {"MELCHIOR": "MEL", "BALTHASAR": "BAL", "CASPER": "CAS", "ARTABAN": "ART"}


def _abbr(name: str) -> str:
    return ABBREV.get(name, name[:3])


def render_progress(message: str) -> None:
    print(f"{C.GREY}probe :: {message}{C.RESET}", flush=True)


def render_agreement_matrix(report: ProbeReport, phase: str) -> None:
    members = report.members
    pairs = pairwise_agreement(report.samples, members, phase)

    label = "ROUND 1" if phase == PHASE_ROUND1 else "AFTER REFLECTION"
    print(f"\n{C.BOLD}PAIRWISE AGREEMENT :: {label}{C.RESET}")
    print(f"{C.GREY}(fraction of samples the pair voted the same; 1.00 = one voice){C.RESET}\n")

    header = "        " + "".join(f"{_abbr(m):>7}" for m in members)
    print(header)
    for a in members:
        row = f"  {_abbr(a):<6}"
        for b in members:
            if a == b:
                row += f"{C.GREY}{'—':>7}{C.RESET}"
                continue
            value = pairs[tuple(sorted((a, b)))]
            color = C.RED if value >= COLLAPSE_AGREEMENT else C.RESET
            row += f"{color}{value:>7.2f}{C.RESET}"
        print(row)

    flagged = [
        (a, b, v)
        for (a, b), v in pairs.items()
        if v >= COLLAPSE_AGREEMENT
    ]
    if flagged:
        print(f"\n{C.RED}Possible facet collapse:{C.RESET}")
        for a, b, v in flagged:
            print(f"  {a} / {b} agree {v:.0%} of the time — behaving as one voice.")
    else:
        print(f"\n{C.GREEN}No pair exceeds the collapse threshold "
              f"({COLLAPSE_AGREEMENT:.0%}). The voices are distinct.{C.RESET}")


def render_member_table(report: ProbeReport, phase: str) -> None:
    members = report.members
    stab = member_stability(report.samples, members, phase)
    aff = affirmative_rate(report.samples, members, phase)
    conf = mean_confidence(report.samples, members, phase)

    print(f"\n{C.BOLD}PER-MEMBER PROFILE{C.RESET}")
    print(f"{C.GREY}stability = vote consistency across repetitions of the same proposition{C.RESET}\n")
    print(f"  {'MEMBER':<12}{'STABILITY':>11}{'AFFIRM RATE':>13}{'MEAN CONF':>11}")
    for m in members:
        stab_color = C.RED if stab[m] < NOISY_STABILITY else C.RESET
        stuck = aff[m] in (0.0, 1.0) and len(report.propositions) > 1
        aff_color = C.AMBER if stuck else C.RESET
        print(
            f"  {m:<12}"
            f"{stab_color}{stab[m]:>11.2f}{C.RESET}"
            f"{aff_color}{aff[m]:>13.2f}{C.RESET}"
            f"{conf[m]:>11.1f}"
        )

    noisy = [m for m in members if stab[m] < NOISY_STABILITY]
    if noisy:
        print(f"\n{C.RED}Noisy voices (single runs unreliable):{C.RESET} {', '.join(noisy)}")
    stuck = [m for m in members if aff[m] in (0.0, 1.0) and len(report.propositions) > 1]
    if stuck:
        print(f"{C.AMBER}Never changes vote across diverse propositions:{C.RESET} "
              f"{', '.join(stuck)} — check facet binding or silent-default votes.")


def render_report(report: ProbeReport) -> None:
    print(f"\n{C.AMBER}{'═' * 72}{C.RESET}")
    print(f"{C.AMBER}{C.BOLD}MAGI INDEPENDENCE PROBE{C.RESET}")
    print(f"{C.AMBER}{'═' * 72}{C.RESET}")
    print(f"  propositions: {len(report.propositions)}   "
          f"repetitions: {report.repetitions}   "
          f"samples: {len(report.samples)}   "
          f"mode: {'full (with reflection)' if report.full else 'round-1 only'}")

    if report.repetitions < 3:
        print(f"\n{C.AMBER}Note: with fewer than 3 repetitions, stability is not "
              f"meaningful. Use -k 5 for real measurement.{C.RESET}")

    render_agreement_matrix(report, PHASE_ROUND1)
    render_member_table(report, PHASE_ROUND1)

    if report.full:
        render_agreement_matrix(report, PHASE_REFLECTED)
        delta = convergence(report.samples, report.members)
        if delta is not None:
            color = C.RED if delta > 0.15 else C.GREEN
            print(f"\n{C.BOLD}DEBATE CONVERGENCE:{C.RESET} "
                  f"{color}{delta:+.2f}{C.RESET} "
                  f"{C.GREY}(agreement after reflection minus before; "
                  f"large positive = council talks itself into one mind){C.RESET}")

    print(f"\n{C.AMBER}{'═' * 72}{C.RESET}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Measure MAGI council independence.")
    parser.add_argument("propositions", nargs="*", help="Propositions to probe (default: built-in diagnostic set).")
    parser.add_argument("-k", "--repetitions", type=int, default=5, help="Repetitions per proposition (default 5).")
    parser.add_argument("--full", action="store_true", help="Run full protocol and also measure post-reflection convergence.")
    parser.add_argument("--mock", action="store_true", help="Use the mock backend (validates the harness; deterministic).")
    parser.add_argument("--same", action="store_true", help="Use the default model for all members.")
    parser.add_argument("--model", default=None, help="Force all members to use one model.")
    args = parser.parse_args()

    propositions = args.propositions or list(DEFAULT_PROPOSITIONS)

    try:
        engine = MagiEngine(model=args.model, mock=args.mock, same=args.same)
        report = run_probe(
            engine=engine,
            propositions=propositions,
            repetitions=args.repetitions,
            full=args.full,
            progress=render_progress,
        )
    except OllamaError as exc:
        print(f"{C.RED}{C.BOLD}Probe could not run with Ollama.{C.RESET}\n")
        print(exc)
        print("\nUse mock mode to validate the harness:\n"
              "  python scripts/probe.py --mock -k 5\n")
        sys.exit(1)

    render_report(report)


if __name__ == "__main__":
    main()
