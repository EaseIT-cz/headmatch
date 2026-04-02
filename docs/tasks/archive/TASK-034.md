# TASK-034 — Add guided troubleshooting hints for low-confidence runs

## Summary
When a run has low confidence or warnings, give users a short, practical troubleshooting guide based on the existing confidence summary so they know what to try next.

## Context
Confidence is now surfaced in both the GUI and CLI. The next product step is to help users recover from suspicious or noisy runs instead of just telling them something looks wrong. The existing confidence summary already includes headline, interpretation, warnings, and metrics; this task should build on that rather than invent a new scoring system.

## Scope
- Add concise troubleshooting guidance derived from the existing confidence summary and warnings.
- Surface it in the user-facing outputs where it is most useful.
- Keep the guidance simple and practical for non-technical audio enthusiasts.
- Update tests as needed.

## Out of scope
- New confidence heuristics.
- Full troubleshooting wizard or branching flow engine.
- Major GUI/CLI redesign.
- Deep PipeWire device-detection changes.

## Acceptance criteria
- Low-confidence or warning-heavy runs include practical next-step guidance.
- Guidance is tied to the existing summary/warnings, not a separate hidden system.
- The change remains conservative and easy to understand.
- Full test suite passes.

## Suggested files/components
- `headmatch/pipeline.py`
- `headmatch/cli.py`
- `headmatch/gui_views.py` if needed
- `tests/test_pipeline.py`
- `tests/test_cli.py`
- `tests/test_gui.py` if needed
