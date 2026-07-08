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

Current phase: **v0.2.0-alpha — Local Deliberation Engine**

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


---

## Current Milestone

### v0.2.0-alpha — Local Deliberation Engine

MAGI now supports real local Ollama execution, JSON-mode robustness, progress indicators, improved council prompts, self-question prevention, and a structured final-vote record for the non-voting Chair.

See [`docs/releases/v0.2.0-alpha.md`](docs/releases/v0.2.0-alpha.md) for release notes.

MAGI currently supports a complete mock-mode deliberation protocol:

1. Independent analysis
2. Cross-examination
3. Satisfaction evaluation
4. Reflection
5. Non-voting Chair dossier

Run a mock deliberation:

```bash
python scripts/magi_cli.py --mock "Should MAGI preserve minority reports?"

Run tests:

python -m unittest discover tests

The current release proves protocol correctness, not intelligence quality.

---

## Running with Ollama

MAGI can run in two modes:

### Mock mode

Mock mode does not require Ollama or any local model.

```bash
python scripts/magi_cli.py --mock "Should MAGI preserve minority reports?"
Mock mode is useful for testing the protocol.

Real local model mode

Install and run Ollama first.

Check whether Ollama is reachable:

python scripts/magi_cli.py --check-ollama

List installed models:

python scripts/magi_cli.py --list-models

Install a basic model:

ollama pull llama3.2

Run MAGI with one model for the whole council:

python scripts/magi_cli.py --model llama3.2 "Should MAGI preserve minority reports?"

Run MAGI with the default model for all members:

python scripts/magi_cli.py --same "Should MAGI preserve minority reports?"

Run MAGI with preferred council models when available:

python scripts/magi_cli.py "Should MAGI preserve minority reports?"

Preferred models are currently:

MELCHIOR → qwen2.5
BALTHASAR → gemma2
CASPER → mistral
ARTABAN → llama3.1

If a preferred model is unavailable, MAGI attempts a safe fallback and reports the fallback in the terminal output.
