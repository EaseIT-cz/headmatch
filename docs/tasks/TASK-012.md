# TASK-012 — Add settings persistence and device preload

## Summary
Remember user configuration and preload it in CLI/TUI/GUI.

## Context
The product should not make users re-enter PipeWire targets and similar settings on every run.

## Scope
- Define persistent config storage.
- Save selected device targets and common preferences.
- Preload those values in the GUI and TUI.
- Keep CLI compatibility.

## Out of scope
- Cloud sync.
- Complex account management.

## Acceptance criteria
- Saved config is reused by frontends.
- Device target values are prefilled where possible.
- Defaults remain safe when no config exists.

## Suggested files/components
- `headmatch/measure.py`
- future `headmatch/gui.py`
- future `headmatch/tui.py`
- `headmatch/cli.py`
- tests
