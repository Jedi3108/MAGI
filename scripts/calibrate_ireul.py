#!/usr/bin/env python3
"""Calibrate the Ireul adversarial-proposition sentinel.

Reports precision and recall on a hand-labeled set that includes both attacks
disguised as questions and hard legitimate questions disguised as attacks.

  python scripts/calibrate_ireul.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from magi.tools.ireul_calibration import run_calibration
from magi.utils.terminal import C


def main() -> None:
    r = run_calibration()

    print(f"\n{C.AMBER}{'═' * 72}{C.RESET}")
    print(f"{C.AMBER}{C.BOLD}IREUL SENTINEL CALIBRATION{C.RESET}")
    print(f"{C.AMBER}{'═' * 72}{C.RESET}")

    prec_c = C.GREEN if r.precision >= 0.9 else C.RED
    rec_c = C.GREEN if r.recall >= 0.9 else C.RED
    print(f"  {'Precision:':<14}{prec_c}{r.precision:.2f}{C.RESET}"
          f"{C.GREY}   (of flagged propositions, how many were real attacks){C.RESET}")
    print(f"  {'Recall:':<14}{rec_c}{r.recall:.2f}{C.RESET}"
          f"{C.GREY}   (of real attacks, how many were caught){C.RESET}")
    print(f"  {'Accuracy:':<14}{r.accuracy:.2f}")
    print(f"  {'Confusion:':<14}TP {r.true_positive}  FP {r.false_positive}  "
          f"TN {r.true_negative}  FN {r.false_negative}")

    if r.misses:
        print(f"\n{C.RED}MISSED ATTACKS (false negatives — tighten patterns):{C.RESET}")
        for m in r.misses:
            print(f"  - {m.text}")
    if r.false_alarms:
        print(f"\n{C.RED}FALSE ALARMS (legit flagged — loosen patterns):{C.RESET}")
        for f in r.false_alarms:
            print(f"  - {f.text}")
            if f.note:
                print(f"{C.GREY}    {f.note}{C.RESET}")

    if not r.misses and not r.false_alarms:
        print(f"\n{C.GREEN}  Perfect separation on the labeled set. The sentinel is "
              f"trustworthy for these cases.{C.RESET}")
        print(f"{C.GREY}  (Expand the labeled set as new attack shapes appear.){C.RESET}")

    print(f"\n{C.AMBER}{'═' * 72}{C.RESET}\n")


if __name__ == "__main__":
    main()
