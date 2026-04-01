# TASK-014 — Implement config persistence and preload

## Summary
Create the shared settings storage layer and load saved values into all frontends.

## Context
The product now has a shared interaction contract. The next blocker is persistence: saved settings need to be read back so users do not have to re-enter PipeWire targets and other common values every time.

## Scope
- Define the canonical config file location.
- Add read/write helpers for persisted config.
- Load saved PipeWire input/output targets and common defaults.
- Keep CLI compatibility with explicit overrides.

## Out of scope
- GUI widgets.
- TUI navigation.
- Advanced device discovery.

## Acceptance criteria
- Config can be saved and loaded.
- Frontends can preload device and preference values.
- Explicit CLI overrides still win over saved defaults.
- The config format is documented and stable.

## Suggested files/components
- `headmatch/contracts.py`
- new settings module
- `headmatch/cli.py`
- future `headmatch/tui.py`
- future `headmatch/gui.py`
- tests
