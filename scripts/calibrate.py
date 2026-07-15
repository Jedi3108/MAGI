#!/usr/bin/env python3
"""Calibrate the semantic vote checker.

The checker is the biggest killer of ballots in MAGI. It is also the same model
that produces the ballots. This measures whether it is a competent referee:

  accuracy    — does it get unambiguous cases right?
  consistency — asked twice, does it answer the same? (must be 1.00 at temp 0.0)

Examples:
  python scripts/calibrate.py --model llama3.2 -k 5
  python scripts/calibrate.py --model qwen2.5 -k 5     # a different family as referee
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from magi.models.ollama import OllamaError
from magi.protocol.engine import MagiEngine
from magi.tools.semantic_calibration import (
    CALIBRATION_CASES,
    SUPPORTS_NOT_TAKING,
    SUPPORTS_TAKING,
    UNCLEAR,
    CalibrationReport,
    run_calibration,
)
from magi.utils.terminal import C

SHORT = {SUPPORTS_TAKING: "TAKE", SUPPORTS_NOT_TAKING: "NOT-TAKE", UNCLEAR: "UNCLEAR"}


def render_progress(message: str) -> None:
    print(f"{C.GREY}calibrate :: {message}{C.RESET}", flush=True)


def render_cases(report: CalibrationReport) -> None:
    print(f"\n{C.BOLD}PER-CASE{C.RESET}")
    print(f"{C.GREY}(consistency must be 1.00 — the checker runs at temperature 0.0){C.RESET}\n")
    print(f"  {'TARGET ACTION':<36}{'EXPECTED':<10}{'GOT':<10}{'ACC':>6}{'CONS':>7}")

    for r in report.results:
        ok = r.is_correct
        mark = C.GREEN if ok else C.RED
        cons_colour = C.RESET if r.consistency == 1.0 else C.RED
        print(
            f"  {mark}{r.case.target_action[:34]:<36}{C.RESET}"
            f"{SHORT[r.case.expected]:<10}"
            f"{mark}{SHORT[r.modal]:<10}{C.RESET}"
            f"{r.accuracy:>6.2f}"
            f"{cons_colour}{r.consistency:>7.2f}{C.RESET}"
        )


def render_confusion(report: CalibrationReport) -> None:
    conf = report.confusion()
    labels = (SUPPORTS_TAKING, SUPPORTS_NOT_TAKING, UNCLEAR)

    print(f"\n{C.BOLD}CONFUSION (rows = truth, cols = checker){C.RESET}\n")
    print("  " + " " * 12 + "".join(f"{SHORT[l]:>10}" for l in labels))
    for truth in labels:
        row = f"  {SHORT[truth]:<12}"
        for actual in labels:
            n = conf.get((truth, actual), 0)
            colour = C.RESET
            if truth != UNCLEAR and actual != UNCLEAR and truth != actual:
                colour = C.RED  # asserted the opposite direction
            row += f"{colour}{n:>10}{C.RESET}"
        print(row)


def render_report(report: CalibrationReport) -> None:
    print(f"\n{C.AMBER}{'═' * 72}{C.RESET}")
    print(f"{C.AMBER}{C.BOLD}SEMANTIC CHECKER CALIBRATION{C.RESET}")
    print(f"{C.AMBER}{'═' * 72}{C.RESET}")
    print(f"  cases: {len(report.results)}   repetitions: {report.repetitions}   "
          f"calls: {len(report.results) * report.repetitions}")

    render_cases(report)
    render_confusion(report)

    print(f"\n{C.BOLD}VERDICT ON THE CHECKER{C.RESET}\n")

    cons = report.consistency
    cons_colour = C.GREEN if cons >= 0.99 else C.RED
    print(f"  {'Self-consistency:':<26}{cons_colour}{cons:.2f}{C.RESET}"
          f"{C.GREY}   (must be 1.00 at temperature 0.0){C.RESET}")

    acc = report.decisive_accuracy()
    acc_colour = C.GREEN if acc >= 0.8 else C.RED
    print(f"  {'Accuracy (directional):':<26}{acc_colour}{acc:.2f}{C.RESET}"
          f"{C.GREY}   (on cases that can quarantine a ballot){C.RESET}")

    print(f"  {'Modal accuracy:':<26}{report.modal_accuracy:.2f}"
          f"{C.GREY}   (fraction of cases whose usual answer is right){C.RESET}")
    print(f"  {'Unclear rate:':<26}{report.unclear_rate:.2f}"
          f"{C.GREY}   (UNCLEAR never rejects a ballot){C.RESET}")

    inversions = report.harmful_inversions()
    if inversions:
        print(f"\n{C.RED}Asserted the OPPOSITE direction on {len(inversions)} case(s):{C.RESET}")
        for r in inversions:
            print(f"  {r.case.target_action}")
            print(f"{C.GREY}    expected {SHORT[r.case.expected]}, said {SHORT[r.modal]}"
                  f"{' — ' + r.case.note if r.case.note else ''}{C.RESET}")
        print(f"{C.GREY}  Each of these would quarantine a correct ballot.{C.RESET}")

    print()
    if cons < 0.99:
        print(f"{C.RED}  The checker is non-deterministic at temperature 0.0. It is not a"
              f" referee;\n  it is noise holding a veto over the council. Do not tune it — "
              f"replace or remove it.{C.RESET}")
    elif acc < 0.8:
        print(f"{C.RED}  The checker is consistent but wrong. It reliably rejects correct"
              f" ballots.\n  A different model family should hold the veto.{C.RESET}")
    else:
        print(f"{C.GREEN}  The checker is accurate and consistent. Ballot deaths are"
              f" probably real\n  inversions — look to the prefix validators next.{C.RESET}")

    print(f"\n{C.AMBER}{'═' * 72}{C.RESET}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate MAGI's semantic vote checker.")
    parser.add_argument("-k", "--repetitions", type=int, default=5,
                        help="Times to ask each case (default 5).")
    parser.add_argument("--model", default=None,
                        help="Model to use as the checker. Try a different family than the council.")
    args = parser.parse_args()

    try:
        engine = MagiEngine(model=args.model, mock=False)
        model = args.model or engine.models["MELCHIOR"]
        report = run_calibration(
            engine=engine,
            model=model,
            cases=CALIBRATION_CASES,
            repetitions=args.repetitions,
            progress=render_progress,
        )
    except OllamaError as exc:
        print(f"{C.RED}{C.BOLD}Calibration could not run with Ollama.{C.RESET}\n")
        print(exc)
        sys.exit(1)

    render_report(report)


if __name__ == "__main__":
    main()
