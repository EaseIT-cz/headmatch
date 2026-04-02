# TASK-054 — Reject mono or duplicated-channel captures during analysis

## Summary
Prevent misleading headphone fits by rejecting mono or effectively duplicated-channel captures during measurement analysis instead of silently treating them as valid stereo data.

## Context
Real-world sample data showed a suspicious pattern:
- `measurement_left.csv` and `measurement_right.csv` were identical
- raw left/right traces were also identical
- confidence still reported the run as usable enough to proceed

The backend currently accepts mono recordings by duplicating the single channel to stereo, which can hide a broken capture chain and produce misleading clone/EQ results.

## Scope
- Stop silently duplicating mono recordings in the analysis path.
- Detect obviously duplicated stereo channel captures and fail with an actionable error.
- Add regression tests for both failure modes.
- Keep the fix focused on backend correctness and user safety.

## Out of scope
- GUI redesign.
- New measurement algorithms.
- Relaxed fallback modes for advanced users.

## Acceptance criteria
- Mono captures are rejected with a clear actionable message.
- Obviously duplicated stereo captures are rejected with a clear actionable message.
- Existing real stereo workflows remain valid.
- Full test suite passes.

## Suggested files/components
- `headmatch/analysis.py`
- `tests/test_pipeline.py`
- `tests/test_integration_cli.py` if useful
