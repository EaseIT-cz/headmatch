# TASK-036 — Add a simple GUI run-comparison view in history

## Summary
Help users compare two recent runs in the GUI history flow so they can more easily judge whether one run or preset looks better than another.

## Context
The next active backlog item is run/preset comparison. HeadMatch already has GUI history browsing and stable run summaries, but users still have to inspect folders manually when they want to compare two results. A small GUI-first comparison slice is the right next step.

## Scope
- Add a simple GUI history comparison view or panel for two runs.
- Base the comparison on existing summary/report artifacts rather than new analysis heuristics.
- Focus on the most useful differences for a first slice, such as target, filter counts, predicted error, and confidence/trust summary.
- Update tests as needed.

## Out of scope
- New DSP or scoring heuristics.
- Full graph diffing.
- TUI comparison work.
- Major history redesign.

## Acceptance criteria
- A GUI user can compare two runs without manually opening multiple folders first.
- The comparison uses existing artifacts as the source of truth.
- The first slice is simple and practical, not overdesigned.
- Full test suite passes.

## Suggested files/components
- `headmatch/history.py`
- `headmatch/gui.py`
- `headmatch/gui_views.py`
- `headmatch/contracts.py` if needed
- `tests/test_gui.py`
- `tests/test_history.py`
