# TASK-022 — Strengthen alignment and synthetic robustness tests

## Summary
Improve sweep alignment reliability and add synthetic tests for noisy, delayed, or imbalanced recordings.

## Context
Even with better import handling, the analysis pipeline still needs to stay stable when real measurements are messy.

## Scope
- Improve alignment / sweep detection for noisy or delayed recordings.
- Add synthetic tests for delay, noise, and left/right imbalance.
- Keep the fitter inputs stable and predictable.

## Out of scope
- New measurement workflows.
- Visual analysis tools.
- Broad algorithm redesign beyond targeted robustness fixes.

## Acceptance criteria
- Alignment behavior is more tolerant of realistic recordings.
- Tests cover the new scenarios.
- Existing mainline workflows remain compatible.

## Suggested files/components
- `headmatch/analysis.py`
- `headmatch/signals.py`
- `tests/`
