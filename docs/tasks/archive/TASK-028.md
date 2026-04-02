# TASK-028 — Add result interpretation and confidence scoring

## Summary
Add a user-facing quality/confidence layer so HeadMatch can tell users whether a run looks trustworthy.

## Context
The product now produces measurements, fit reports, graphs, and exports, but users still have to decide for themselves whether a result is reliable. For the intended audience, that is too much hidden judgment.

## Scope
- Define a small confidence model for measurement/fit quality.
- Add user-facing interpretation fields to run outputs.
- Surface warnings for suspicious results such as noise, alignment weakness, or large channel mismatch.
- Keep the scoring simple, explainable, and conservative.

## Out of scope
- Full troubleshooting wizard.
- Major analysis redesign.
- UI redesign.

## Acceptance criteria
- Fit outputs include a confidence / interpretation summary.
- The summary is readable by non-technical users.
- The scoring is derived from observable metrics, not arbitrary labels.
- The result is surfaced in the CLI and GUI.
- Tests cover both strong and suspicious runs.

## Suggested files/components
- `headmatch/analysis.py`
- `headmatch/pipeline.py`
- `headmatch/gui.py`
- `headmatch/cli.py`
- `README.md`
- `tests/`
