# TASK-059 — Extend duplicated-channel detection to multichannel captures

## Summary
The duplicated-channel check added in TASK-054 only fires for exactly 2-channel files. Multichannel recordings (3+ channels) silently use channels 0 and 1 without verifying they are distinct.

## Context
`_coerce_measurement_audio` in `analysis.py` checks for identical L/R when `data.shape[1] == 2`, but the `data.shape[1] >= 2` branch (for 3+ channels) skips that check entirely. A multichannel capture where channels 0 and 1 are identical would pass through undetected.

## Scope
- Move the `np.allclose` duplicated-channel check so it also applies after slicing the first two channels from multichannel recordings.

## Out of scope
- Changing error messages or validation thresholds.
- Detecting other multichannel anomalies (e.g., all channels identical).

## Acceptance criteria
- A 4-channel file where channels 0 and 1 are identical is rejected with the same duplicated-channel error.
- Existing multichannel tests continue to pass.
- Full test suite passes.

## Suggested files/components
- `headmatch/analysis.py`
- `tests/test_pipeline.py`
