# TASK-032 — Surface confidence more clearly in the GUI

## Summary
Make the confidence/trust summary more visible and more useful in the GUI so non-technical users can quickly tell whether a run looks trustworthy.

## Context
The backend confidence summary now exists and the recent refactor work has reduced structural risk in both the pipeline and the GUI. The product strategy is GUI-first, and the active backlog item is to surface confidence and interpretation more clearly in the GUI and CLI. The GUI should therefore get the first presentation pass.

## Scope
- Surface the confidence label/score/headline more prominently in the GUI where users review recent runs.
- Show the most useful warnings or interpretation text without forcing users to open JSON files first.
- Reuse the existing run-summary contract and keep the implementation simple.
- Update tests as needed.

## Out of scope
- New confidence heuristics.
- CLI changes.
- Troubleshooting flow design beyond basic guidance already present in the confidence summary.
- Broad GUI redesign.

## Acceptance criteria
- The GUI makes confidence/trust status visible during result review/history browsing.
- Users can see at least the confidence level and a short interpretation without opening `run_summary.json` manually.
- Existing run-summary JSON remains the source of truth.
- GUI tests cover the new presentation behavior.
- Full test suite passes.

## Suggested files/components
- `headmatch/gui.py`
- `headmatch/gui_views.py`
- `headmatch/contracts.py`
- `headmatch/history.py` if needed
- `tests/test_gui.py`
- `tests/test_history.py` if needed
