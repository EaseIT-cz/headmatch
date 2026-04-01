# TASK-018 — Add shared config preload to TUI and GUI

## Summary
Wire saved configuration into the TUI and GUI startup flow.

## Context
Once persistence exists, the interactive frontends need to consume it consistently so users see their previous device choices and preferences prefilled.

## Scope
- Load saved config into both frontends.
- Prepopulate device target fields.
- Show safe defaults when no config exists.
- Keep CLI overrides supported.

## Out of scope
- Advanced settings editor.
- Device auto-detection redesign.

## Acceptance criteria
- TUI and GUI both show preloaded values.
- The defaults are obvious when no config exists.
- The behavior matches the shared contract.

## Suggested files/components
- future `headmatch/tui.py`
- future `headmatch/gui.py`
- new settings module
- tests
