# TASK-044 — Make the GUI left navigation a compact label-only sidebar

## Summary
Fix the GUI left navigation so it behaves like a compact sidebar: short label-only buttons, consistent left alignment, no redundant descriptions, and materially less screen usage.

## Context
The previous GUI cleanup improved labels and theme adoption, but the left navigation still takes too much space and still renders redundant descriptive copy inside the buttons. The current indentation/alignment is also inconsistent between entries. The user wants a true compact navigation sidebar.

## Scope
- Remove descriptive text from the left navigation buttons entirely.
- Keep only short labels:
  - `Measure`
  - `Prepare Offline`
  - `Results`
- Make the sidebar materially narrower / less dominant.
- Ensure all nav buttons share consistent left alignment and spacing.
- Update tests as needed.

## Out of scope
- Broad GUI redesign beyond the left navigation.
- Backend, CLI, or TUI changes.
- New workflow logic.

## Acceptance criteria
- Navigation buttons show labels only, with no descriptions inside the buttons.
- Sidebar occupies less screen space and no longer dominates the layout.
- All nav buttons align consistently.
- Full test suite passes.

## Suggested files/components
- `headmatch/gui.py`
- `headmatch/gui_views.py`
- `tests/test_gui.py`
