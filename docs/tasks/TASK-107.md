# TASK-107 - Extract GUI workflow controllers from HeadMatchGuiApp

## Summary
Split workflow-specific orchestration out of `HeadMatchGuiApp` so the shell focuses on app bootstrap, navigation, and shared services.

## Context
`HeadMatchGuiApp` currently owns navigation, file picking, background tasks, online/offline measurement, clone target creation, APO import/refine, fetch curve, history, and completion/progress handling. That concentration makes bugs and regressions more likely.

## Scope
- Extract workflow-specific controller/helper classes or modules for at least:
  - online measurement
  - offline workflow
  - clone target workflow
  - APO import/refine
  - fetch curve/history if natural
- Keep `HeadMatchGuiApp` as the shell/composition root
- Reduce method count and complexity in `HeadMatchGuiApp`
- Preserve public GUI entry points and user-visible behavior
- Add/update tests for extracted controller behavior through GUI tests or focused unit tests

## Out of scope
- Replacing view routing with a registry
- Major UI redesign
- Backend changes unrelated to controller extraction

## Acceptance criteria
- `HeadMatchGuiApp` is materially smaller and focused on shell duties
- Workflow orchestration logic is moved into dedicated modules/classes
- Full test suite passes
- Extracted code is covered by tests in touched areas

## Suggested files/components
- `headmatch/gui/shell.py`
- `headmatch/gui/controllers/`
- `tests/test_gui.py`
