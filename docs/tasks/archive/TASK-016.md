# TASK-016 — Build the initial TUI wizard

## Summary
Create the first keyboard-driven guided workflow for headmatch.

## Context
The TUI should help users step through measurement without needing to remember commands. It should be a guided middle ground between CLI and GUI.

## Scope
- Create the TUI entry point.
- Implement a beginner-friendly wizard flow.
- Support online and offline entry paths.
- Show basic progress and next-step guidance.

## Out of scope
- Graphical UI widgets.
- Full settings editor.
- Advanced device discovery.

## Acceptance criteria
- Users can start a guided run from the TUI.
- The TUI has a simple beginner path.
- It can read preloaded device values.
- It reuses the shared backend pipeline.

## Suggested files/components
- future `headmatch/tui.py`
- `headmatch/pipeline.py`
- `headmatch/measure.py`
- `headmatch/targets.py`
- tests
