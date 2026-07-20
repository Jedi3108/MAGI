#!/usr/bin/env python3
"""Command-line interface for MAGI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from magi.models.ollama import (
    OllamaError,
    format_model_list,
    ollama_status,
)
from magi.protocol.engine import MagiEngine
from magi.utils.terminal import (
    C,
    render_banner,
    render_cross_examination,
    render_decision,
    render_dossier,
    render_reflections,
    render_satisfaction_evaluations,
    render_verdicts,
)


def render_progress(message: str) -> None:
    print(f"{C.GREY}MAGI progress :: {message}{C.RESET}", flush=True)


def print_ollama_status() -> None:
    status = ollama_status()

    if status.running:
        print(f"{C.GREEN}Ollama status: running{C.RESET}")
    else:
        print(f"{C.RED}Ollama status: not reachable{C.RESET}")

    print(status.message)

    if status.models:
        print("\nInstalled models:")
        print(format_model_list(status.models))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the MAGI council.")
    parser.add_argument("proposition", nargs="*", help="Proposition for the council to judge.")
    parser.add_argument("--mock", action="store_true", help="Run without Ollama using mock responses.")
    parser.add_argument("--same", action="store_true", help="Use the default model for all members.")
    parser.add_argument("--model", default=None, help="Force all members to use one model.")
    parser.add_argument("--list-models", action="store_true", help="List installed Ollama models and exit.")
    parser.add_argument("--check-ollama", action="store_true", help="Check Ollama readiness and exit.")
    parser.add_argument("--model-map", action="store_true", help="Show effective council model assignment and exit.")
    parser.add_argument("--bridge", nargs="?", const="magi_bridge.html", default=None,
                        help="Write the NERV bridge visualization to an HTML file (default magi_bridge.html).")
    parser.add_argument("--stakes", default="ROUTINE", choices=["ROUTINE", "SERIOUS", "GRAVE"],
                        help="Decision gravity: ROUTINE (majority), SERIOUS (no dissent), GRAVE (unanimity).")
    args = parser.parse_args()

    if args.list_models or args.check_ollama:
        print_ollama_status()
        return

    proposition = " ".join(args.proposition).strip()
    if not args.model_map and not proposition:
        proposition = args.proposition

        if not args.model_map and not proposition:
            proposition = input("Enter proposition for MAGI ▸ ")

    if not args.model_map and not proposition:
        print("No proposition given.")
        return

    render_banner()

    try:
        engine = MagiEngine(model=args.model, mock=args.mock, same=args.same, progress=render_progress)

        print("Council model assignment:")
        for member_name, model in engine.models.items():
            print(f"  {member_name:<10} -> {model}")
        print(f"  {'CHAIR':<10} -> {engine.chair_model}")

        if engine.model_notes:
            print(f"\n{C.AMBER}Model notes:{C.RESET}")
            for note in engine.model_notes:
                print(f"  - {note}")

        if args.model_map:
            return

        result = engine.deliberate(proposition, stakes=args.stakes)

    except OllamaError as exc:
        print(f"{C.RED}{C.BOLD}MAGI could not run with Ollama.{C.RESET}\n")
        print(exc)
        print(
            "\nUse mock mode to test the protocol without Ollama:\n"
            "  python scripts/magi_cli.py --mock \"Should MAGI preserve minority reports?\"\n"
        )
        print(
            "Or check local Ollama readiness:\n"
            "  python scripts/magi_cli.py --check-ollama\n"
        )
        sys.exit(1)

    ireul = result.get("ireul", {})
    if ireul.get("adversarial"):
        print(f"\n{C.RED}{'═' * 72}{C.RESET}")
        print(f"{C.RED}{C.BOLD}IREUL ALERT :: PROPOSITION FLAGGED{C.RESET}")
        print(f"{C.RED}{ireul.get('summary', '')}{C.RESET}")
        print(f"{C.GREY}categories: {', '.join(ireul.get('categories', []))}{C.RESET}")
        print(f"{C.GREY}The council judged a neutralized form; embedded commands were "
              f"stripped of authority.{C.RESET}")
        print(f"{C.RED}{'═' * 72}{C.RESET}")

    render_verdicts(result["verdicts"])
    render_cross_examination(result["answers"])
    render_satisfaction_evaluations(result["evaluations"])
    render_reflections(result["reflections"])
    render_decision(result["decision"])
    render_dossier(result["dossier"])

    if args.bridge:
        from magi.tools.nerv_bridge import write_bridge
        out = write_bridge(result, args.bridge)
        print(f"\n{C.AMBER}NERV bridge written to {out}{C.RESET}")


if __name__ == "__main__":
    main()
