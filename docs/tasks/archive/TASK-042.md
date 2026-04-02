# TASK-042 — Simplify GUI navigation and make results scrollable

## Summary
Streamline the GUI by removing the low-value Home section, starting the app on the guided measurement screen, shortening the navigation labels, and making the results/history area scrollable.

## Context
The current GUI includes a Home section that is not adding enough value relative to the primary workflows. The navigation labels are also too verbose for the available space, and the results/history area needs scrolling once more content is shown.

## Scope
- Remove the Home section from the primary GUI navigation.
- Start the GUI on the guided measurement / online wizard screen.
- Shorten the navigation labels to:
  - `Measure`
  - `Prepare Offline`
  - `Results`
- Add scrolling for the results/history summary area so longer content remains usable.
- Update tests as needed.

## Out of scope
- Broader GUI redesign.
- New backend behavior.
- New history selection logic beyond what is needed for scrolling/presentation.
- CLI or TUI changes.

## Acceptance criteria
- The GUI opens on the guided measurement screen instead of Home.
- The Home section is removed from navigation.
- Navigation labels are shorter and no longer overflow awkwardly.
- Results/history content is scrollable.
- Full test suite passes.

## Suggested files/components
- `headmatch/gui.py`
- `headmatch/gui_views.py`
- `tests/test_gui.py`
