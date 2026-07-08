# Current Status

Current release target: v0.2.0-alpha  
Branch status: release preparation  
Primary branch: develop  
Stable branch: main

## Project state

MAGI is currently a local-first deliberation engine with a four-member council and a non-voting Chair.

The system can run a full deliberation protocol using either deterministic mock outputs or a real local Ollama model.

## Implemented

- Permanent council identities:
  - MELCHIOR — The Scientist
  - BALTHASAR — The Mother
  - CASPER — The Woman
  - ARTABAN — The Man
- Non-voting Chair
- Round 1 independent analysis
- Round 2 cross-examination
- Round 3 satisfaction evaluation
- Round 4 reflection
- Final decision tally
- Chair decision dossier
- Mock backend
- Ollama backend
- Ollama readiness checks
- Installed model listing
- JSON-mode support
- Robust JSON parsing helpers
- Parser fallbacks for malformed model output
- Protocol progress indicators
- Improved council prompts
- Self-question prevention
- Structured final reflected vote record for the Chair
- Unit tests for core protocol behavior

## Verified

The system has been verified with:

```bash
python -m compileall magi scripts
python -m unittest discover tests
python scripts/magi_cli.py --mock "Should MAGI preserve minority reports?"
python scripts/magi_cli.py --model llama3.2 "Should MAGI preserve minority reports?"
Not yet implemented
Long-term memory
External tools
Worker execution layer
Web or desktop UI
Multi-model council optimization
Persistent deliberation logs
Dataset or benchmark evaluation
Human review workflow
Current development priority

Prepare and tag v0.2.0-alpha.

After v0.2.0-alpha, the next likely development focus is either:

persistent deliberation logs, or
multi-model council support.
