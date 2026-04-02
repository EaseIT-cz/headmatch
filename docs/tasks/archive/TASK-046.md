# TASK-046 — Add a first-run environment check entry point to the GUI

## Summary
Add a small GUI-first environment check entry point so users can quickly verify setup readiness without dropping to the terminal first.

## Context
HeadMatch now has `headmatch doctor`, but the product is GUI-first. Installation and release ergonomics remain the active roadmap area, and the next practical step is to expose a simple readiness check from the GUI itself.

## Scope
- Add a small GUI entry point for environment/setup checks.
- Reuse the existing doctor/readiness logic where practical instead of creating a separate system.
- Keep the GUI change simple and beginner-friendly.
- Update tests as needed.

## Out of scope
- Major diagnostics redesign.
- Full settings/preferences system.
- Backend measurement changes.
- Cross-platform packaging work.

## Acceptance criteria
- A GUI user can trigger a readiness/environment check without using the CLI first.
- The implementation reuses existing diagnostics logic where practical.
- The change is small, understandable, and consistent with the GUI-first product direction.
- Full test suite passes.

## Suggested files/components
- `headmatch/gui.py`
- `headmatch/gui_views.py`
- `headmatch/measure.py`
- `tests/test_gui.py`
- `tests/test_measure.py` if needed
