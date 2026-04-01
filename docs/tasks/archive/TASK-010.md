# TASK-010 — Implement the GUI skeleton and navigation

## Summary
Build the GUI from scratch with a simple main screen and primary workflow navigation.

## Context
The GUI is one of the main ways users will interact with the tool. It needs to be approachable, clear, and version-aware.

## Scope
- Create the GUI entry point and shell.
- Build the main navigation structure.
- Show version information prominently.
- Preload configured values such as PipeWire input/output targets.

## Out of scope
- Complex workflow automation.
- TUI browsing.
- Advanced settings editor.

## Acceptance criteria
- The GUI launches and shows the app version.
- It has a clear main entry screen.
- It preloads saved config values when available.
- It is structurally ready for the measurement wizard.

## Suggested files/components
- future `headmatch/gui.py`
- `headmatch/measure.py`
- `headmatch/pipeline.py`
- `headmatch/__init__.py`
- tests
