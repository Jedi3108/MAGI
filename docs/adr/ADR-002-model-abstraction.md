# ADR-002: Identity Is Independent From Model

## Status

Accepted

## Context

Local AI models change rapidly. MAGI should not depend on any single model family.

## Decision

Council identity and model implementation are separate.

For example, MELCHIOR is the scientific reasoning identity. The model behind MELCHIOR may be Qwen, Llama, Gemma, Mistral, or another future model.

## Consequences

- Models can be upgraded without changing council identity.
- MAGI remains model-agnostic.
- Evaluation can compare models within the same role.
