# TASK-007 — Define the shared interaction contract

## Summary
Define how CLI, TUI, and GUI will share backend behavior and configuration.

## Context
The product is moving toward three first-class interaction modes. They need a common contract so the frontends stay consistent and do not diverge.

## Scope
- Specify shared input/output structures for runs.
- Define how saved configuration values are loaded into frontends.
- Document the interaction boundaries between frontends and the core pipeline.
- Decide which settings are common across all modes.

## Out of scope
- Concrete GUI widgets.
- TUI implementation details.
- Packaging.

## Acceptance criteria
- A frontend contract exists in docs.
- The contract names shared config values, especially PipeWire device targets.
- The contract makes reuse across CLI/TUI/GUI straightforward.
- The document is small enough to guide implementation.

## Suggested files/components
- `docs/architecture.md`
- `docs/backlog.md`
- `headmatch/pipeline.py`
- future `headmatch/tui.py`
- future `headmatch/gui.py`
