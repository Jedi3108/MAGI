# MAGI

**A Local Deliberative Intelligence Architecture**

MAGI is a local-first, transparent, model-agnostic deliberative intelligence system.

Instead of relying on a single AI model, MAGI uses a structured council of specialized reasoning agents that analyze, challenge, and justify decisions before action is taken.

## Core Council

- **MELCHIOR** — truth, evidence, science, correctness
- **BALTHASAR** — care, safety, wellbeing, sustainability
- **CASPER** — individuality, intuition, aesthetics, desire
- **ARTABAN** — duty, execution, resolve, responsibility

## Project Status

Current phase: **v0.0.1 — Genesis**

MAGI is currently in foundation setup. The first target milestone is:

**v0.1 — The First Council**

## Principles

- Reason before acting.
- Disagreement is information.
- Every decision leaves a trace.
- Models are replaceable.
- The council reasons; workers act.

## Repository Structure

- `docs/` — philosophy, architecture, protocol, roadmap, ADRs
- `magi/` — core Python package
- `tests/` — tests
- `examples/` — runnable examples
- `experiments/` — unstable ideas
- `ui/` — future interface
- `journal/` — development journal

## Running MAGI

Run the council in offline mock mode:

```bash
python scripts/magi_cli.py --mock "Should MAGI preserve minority reports?"
Run the council with local Ollama:

python scripts/magi_cli.py "Should MAGI preserve minority reports?"

Force all council members to use one model:

python scripts/magi_cli.py --model qwen2.5 "Should MAGI preserve minority reports?"

Run tests:

python -m unittest discover tests

