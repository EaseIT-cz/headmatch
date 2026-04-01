# TASK-006 — Establish versioning and app identity

## Summary
Make the application version visible and reliable across CLI, TUI, GUI, and generated outputs.

## Context
The project currently has a static package version. Users need to know what build they are running, and generated outputs should carry enough identity to support support/debugging.

## Scope
- Define the canonical version source.
- Expose version in CLI, TUI, and GUI.
- Add build metadata when available.
- Include version in generated result metadata.

## Out of scope
- GUI layout work.
- TUI wizard flow.
- Measurement algorithm changes.

## Acceptance criteria
- The app can report its version consistently.
- The version is visible in all user-facing entry points.
- Generated output metadata includes the version.
- Versioning policy is documented.

## Suggested files/components
- `pyproject.toml`
- `headmatch/__init__.py`
- `headmatch/cli.py`
- future `headmatch/tui.py`
- future `headmatch/gui.py`
- `README.md`
- `docs/architecture.md`
