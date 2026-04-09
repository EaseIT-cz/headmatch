# TASK-109 - Decompose gui/shell.py

## Summary
Break `headmatch/gui/shell.py` (1,011 lines) into smaller, focused modules while preserving app bootstrap and navigation behavior.

## Context
`gui/shell.py` is the project's largest single file and handles state management, rendering dispatch, event handling, and workflow coordination. This makes it harder to test, review, and maintain. The code review flagged this as a priority cleanup target.

## Scope
- Extract `GuiState` into its own module (`headmatch/gui/state.py`)
- Break out Tkinter variable initialization into a dedicated setup function
- Consider extracting navigation/routing into a registry-based system
- Keep `shell.py` as the app bootstrap and composition root
- Preserve all public GUI entry points and user-visible behavior
- Add/update tests for extracted components

## Out of scope
- Changing backend logic
- Redesigning workflows
- Modifying view rendering

## Acceptance criteria
- `gui/shell.py` is materially smaller (target: <600 lines)
- `GuiState` exists in a separate module with its own tests
- Full test suite passes
- No behavior regressions in GUI

## Suggested files/components
- `headmatch/gui/shell.py`
- `headmatch/gui/state.py` (new)
- `headmatch/gui/navigation.py` (new, optional)
- `tests/test_gui_state.py` (new)
