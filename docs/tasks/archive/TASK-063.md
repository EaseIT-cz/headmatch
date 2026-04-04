# TASK-063 — Add GUI setup diagnostics view

## Summary
The CLI has `headmatch doctor` for pre-measurement diagnostics. The GUI mentions it in help text but doesn't have an equivalent built-in view. Add one.

## Context
`render_setup_check` in `gui_views.py` already exists and renders a doctor report. The GUI shell in `gui.py` has a "Setup" navigation item that calls it. But the current implementation just runs the check once on view load. It should let the user trigger a refresh and see updated results (e.g., after plugging in a device).

The backend for this already exists: `collect_doctor_checks` and `format_doctor_report` in `measure.py`.

## Scope
- Ensure the Setup view in the GUI calls `collect_doctor_checks` / `format_doctor_report` on every refresh.
- Show the report in a scrollable text area (not a single label that truncates).
- Add a "Refresh" button that re-runs the check.
- Add a "Go to Measure" shortcut button.

## Out of scope
- Adding new doctor checks.
- Changing the report format.
- Real-time device monitoring.

## Acceptance criteria
- The Setup view displays the full doctor report.
- Clicking Refresh re-runs the checks and updates the display.
- Long reports are scrollable.
- Existing GUI tests pass.

## Suggested files/components
- `headmatch/gui.py`
- `headmatch/gui_views.py`
- `tests/test_gui.py`
