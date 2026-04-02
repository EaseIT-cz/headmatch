# TASK-047 — Add a lightweight GUI launch/install help panel

## Summary
Add a small GUI launch/install help surface so GUI-first users can understand how to launch HeadMatch reliably from their desktop setup.

## Context
The repo now includes a `.desktop` example and better docs, but installation and launch ergonomics are still the active roadmap area. After exposing environment checks in the GUI, the next small step is to surface launch/install help where GUI-first users will actually see it.

## Scope
- Add a lightweight GUI help surface for launch/install guidance.
- Reuse existing docs/examples where practical.
- Keep the change small and non-intrusive.
- Update tests as needed.

## Out of scope
- Full packaging/release automation.
- Cross-distro installer support.
- Broad GUI redesign.
- Backend changes.

## Acceptance criteria
- GUI-first users can find launch/install guidance from within the app.
- Guidance is concise and practical.
- The solution remains lightweight and maintainable.
- Full test suite passes.

## Suggested files/components
- `headmatch/gui.py`
- `headmatch/gui_views.py`
- `README.md` if wording needs alignment
- `tests/test_gui.py`
