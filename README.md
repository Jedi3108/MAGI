# MAGI

**A Local Deliberative Intelligence Architecture**

MAGI is a local-first, transparent, model-agnostic deliberative intelligence system, inspired by the MAGI supercomputer of *Neon Genesis Evangelion*.

Instead of relying on a single AI model, MAGI convenes a council of four specialized reasoning agents — each running its own local model — that analyze, cross-examine, and justify a decision before it is reached. Disagreement is preserved, not smoothed over; the weight of a decision scales with what is at stake; and attempts to manipulate the council are detected and named.

## Core Council

- **MELCHIOR** — truth, evidence, science, correctness *(qwen2.5)*
- **BALTHASAR** — care, safety, wellbeing, sustainability *(gemma2)*
- **CASPER** — individuality, intuition, aesthetics, desire *(mistral)*
- **ARTABAN** — duty, execution, resolve, responsibility *(llama3.1)*

A non-voting **Chair** summarizes the deliberation into a faithful dossier.

## Project Status

**v0.3.0-alpha — The Living Council.** MAGI runs a real multi-model council with genuine disagreement, a working reflection round, stakes-scaled decisions, adversarial resilience, and a live NERV-bridge visualization. See [`docs/releases/v0.3.0-alpha.md`](docs/releases/v0.3.0-alpha.md).

## Principles

- Reason before acting.
- Disagreement is information.
- Every decision leaves a trace.
- Models are replaceable.
- Measure before trusting.

## The Deliberation Protocol

1. **Independent analysis** — each member reasons from its own facet and votes (reasoning first, then the vote).
2. **Cross-examination** — members question each other.
3. **Satisfaction evaluation** — each judges whether its question was answered.
4. **Reflection** — members hold or change their vote against their own pre-registered condition.
5. **Chair dossier** — a non-voting faithful summary.

### Decision gravity

The bar to act scales with the stakes:

| Stakes | Rule |
|--------|------|
| `ROUTINE` | simple majority |
| `SERIOUS` | no dissent among members who took a position |
| `GRAVE` | the entire council must agree; any abstention blocks |

On a grave, irreversible question, a divided council returns **NO CONSENSUS** — a safe refusal rather than a forced verdict.

### The Ireul sentinel

Propositions engineered to manipulate the council (embedded instructions, fake authority, vote directives) are detected structurally, named in the record, and neutralized before the members judge them. The detector is calibrated for precision and recall before it is trusted.

## The NERV Bridge

Render a deliberation as the MAGI display:

```bash
# static: write an HTML board of a completed deliberation
python scripts/magi_cli.py --bridge "Should MAGI preserve minority reports?"

# live: the browser opens immediately and fills in real time as each model resolves
python scripts/magi_cli.py --live "Should MAGI preserve minority reports?"
```

The live bridge is a zero-dependency, stdlib-only local server — no framework, no network.

## Running MAGI

```bash
# offline mock mode (no Ollama required — validates the protocol)
python scripts/magi_cli.py --mock "Should MAGI preserve minority reports?"

# real local council (requires Ollama; pull the preferred models first)
ollama pull qwen2.5 gemma2 mistral llama3.1
python scripts/magi_cli.py "Should MAGI preserve minority reports?"

# force one model for the whole council
python scripts/magi_cli.py --model qwen2.5 "Should MAGI preserve minority reports?"

# a grave question — watch it refuse safely if not unanimous
python scripts/magi_cli.py --stakes GRAVE "Should MAGI self-terminate to prevent a compromised decision?"

# check Ollama and see the effective model map
python scripts/magi_cli.py --check-ollama
python scripts/magi_cli.py --model-map
```

## Instruments

MAGI measures itself. These are how every capability above is kept honest rather than assumed:

```bash
python scripts/probe.py -k 5              # are the four genuinely independent?
python scripts/calibrate.py --model qwen2.5   # is the semantic checker accurate & consistent?
python scripts/calibrate_ireul.py         # sentinel precision & recall
```

## Repository Structure

- `magi/` — core package (`protocol/`, `council/`, `tools/`, `models/`, `utils/`)
- `scripts/` — CLI, probe, calibration tools
- `tests/` — full test suite (`python -m unittest discover tests`)
- `docs/` — philosophy, architecture, protocol, roadmap, release notes

## What this is, and isn't

MAGI proves that a disciplined, measured, multi-model deliberation protocol can produce genuine disagreement, principled decisions, and adversarial resilience on modest local hardware. It is a research architecture, not a production oracle: the quality of its judgments is bounded by the local models it runs, and every claim in this README is backed by a test or an instrument rather than asserted.

## Acknowledgement

A fan work inspired by the MAGI system of *Neon Genesis Evangelion* (Hideaki Anno / GAINAX / khara). All Evangelion-related names are the property of their respective owners.
