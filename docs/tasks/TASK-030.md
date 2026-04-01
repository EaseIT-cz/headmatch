# TASK-030 — Split the GUI shell from view rendering

## Summary
Refactor the GUI so the app shell/controller is thinner and the view-rendering logic is broken into smaller, easier-to-maintain pieces.

## Context
`headmatch/gui.py` currently concentrates shell layout, navigation, form state, progress/completion screens, history rendering, and workflow launch logic in one large class. The product strategy is GUI-first, so this file will only get harder to evolve if confidence presentation and troubleshooting flows continue to land on top of the current shape.

## Scope
- Break `gui.py` into a thinner shell/controller plus smaller view-rendering helpers or components.
- Preserve current GUI behavior and copy unless a small cleanup is required by the refactor.
- Keep the backend workflow wiring unchanged.
- Keep tests current and expand them if the new structure needs direct coverage.

## Out of scope
- Redesigning the GUI flow.
- New confidence UX beyond strictly preserving current behavior.
- Pipeline/backend refactors.
- TUI changes.

## Acceptance criteria
- The main GUI app/controller is meaningfully smaller and more focused.
- View rendering responsibilities are split into smaller units with clear boundaries.
- Existing GUI tests pass, with updates/additions as needed.
- Full test suite passes.

## Suggested files/components
- `headmatch/gui.py`
- one or more new GUI helper modules if useful
- `tests/test_gui.py`
