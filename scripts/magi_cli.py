#!/usr/bin/env python3
"""Command-line interface for MAGI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from magi.protocol.engine import DEFAULT_MODEL, MagiEngine
from magi.utils.terminal import render_banner, render_decision, render_verdicts


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the MAGI council.")
    parser.add_argument("proposition", nargs="*", help="Proposition for the council to judge.")
    parser.add_argument("--mock", action="store_true", help="Run without Ollama using mock responses.")
    parser.add_argument("--same", action="store_true", help="Use the default model for all members.")
    parser.add_argument("--model", default=None, help="Force all members to use one model.")
    args = parser.parse_args()

    proposition = " ".join(args.proposition).strip()
    if not proposition:
        proposition = input("Enter proposition for MAGI ▸ ").strip()

    if not proposition:
        print("No proposition given.")
        return

    render_banner()

    engine = MagiEngine(model=args.model, mock=args.mock, same=args.same)

    print("Council model assignment:")
    for member_name, model in engine.models.items():
        print(f"  {member_name:<10} -> {model}")

    result = engine.deliberate(proposition)

    render_verdicts(result["verdicts"])
    render_decision(result["decision"])


if __name__ == "__main__":
    main()
