# TASK-001 — Define the guided beginner workflow

## Summary
Define the product-facing measurement and EQ journey for non-technical audiophiles.

## Context
The repo already has working domain pieces, but the experience is still developer-shaped. The target audience wants a simple, low-confusion path with safe defaults and clear next steps.

## Scope
- Write the exact guided flow for first-time users.
- Define the minimum set of user choices exposed at each step.
- Define the wording of prompts, success messages, and failure messages.
- Define the default path for online and offline capture.

## Out of scope
- Code changes.
- PipeWire integration work.
- EQ algorithm changes.
- UI implementation.

## Acceptance criteria
- The workflow is described as a step-by-step user journey.
- The flow makes simplicity the default.
- Offline capture is clearly positioned as a fallback, not a separate product.
- Each step has a clear user goal and exit condition.
- The document is short enough to use as an implementation reference.

## Suggested files/components
- `docs/architecture.md`
- `docs/backlog.md`
- `README.md`
- future CLI prompts in `headmatch/cli.py`
