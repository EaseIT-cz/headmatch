# TASK-035 — Improve PipeWire device guidance in CLI and GUI

## Summary
Reduce user confusion around PipeWire playback/capture target selection by making device guidance clearer in the CLI and GUI.

## Context
Confidence presentation and troubleshooting guidance are now in place. The next active backlog item is improving PipeWire device discovery and guidance so users can more reliably choose the right playback and capture targets without trial and error.

## Scope
- Improve how PipeWire target guidance is explained in the CLI and/or GUI.
- Reuse the existing discovery behavior (`headmatch list-targets`) where practical.
- Prefer small product-facing guidance improvements over backend redesign.
- Update tests as needed.

## Out of scope
- Rewriting PipeWire discovery itself unless a very small fix is needed.
- Major GUI redesign.
- New measurement backend behavior.
- Non-PipeWire device layers.

## Acceptance criteria
- Users get clearer guidance on how to choose playback/capture targets.
- The change reduces ambiguity without adding much complexity.
- Existing device discovery behavior remains stable unless a small improvement is clearly justified.
- Full test suite passes.

## Suggested files/components
- `headmatch/measure.py`
- `headmatch/cli.py`
- `headmatch/gui.py`
- `headmatch/gui_views.py`
- `tests/test_cli.py`
- `tests/test_gui.py`
- `tests/test_measure.py`
