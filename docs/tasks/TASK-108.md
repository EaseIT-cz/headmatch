# TASK-108 - Centralize GUI file-picking and background task helpers

## Summary
Extract repeated picker and background-task orchestration patterns into reusable helpers.

## Context
The GUI repeats similar logic for choosing files/directories and for launching background work with progress/completion handling. Those patterns should be centralized before more workflows are added.

## Scope
- Centralize file/directory picker helpers used by GUI workflows
- Centralize background task launch/completion helpers used by GUI workflows
- Update existing workflows to use shared helpers
- Add or update tests for the shared helpers via GUI tests or focused unit tests

## Out of scope
- Replacing routing
- Major state-model changes
- UI redesign

## Acceptance criteria
- Picker methods are reduced or simplified significantly
- Background task launch logic is reused instead of open-coded repeatedly
- Full test suite passes
- Touched behavior has test coverage via existing or new tests

## Suggested files/components
- `headmatch/gui/shell.py`
- `headmatch/gui/helpers/` or `headmatch/gui/services/`
- `tests/test_gui.py`
