# TASK-067 — Add multi-pass averaging iteration mode

## Summary
Replace the current independent-repeat iteration logic with an averaging mode that measures N times and fits once against the averaged frequency response.

## Context
`iterative_measure_and_fit` in `pipeline.py` currently runs N independent measure→fit cycles with no interaction between them. Each iteration produces its own EQ — there's no averaging or feedback.

Averaging multiple measurements before fitting reduces random noise from head position variation, ambient noise, and mic placement inconsistency. This directly improves fit quality.

## Scope
- Add a new iteration mode (e.g., `--iteration-mode average`) that:
  1. Runs N measurements (play sweep, record, analyze).
  2. Averages the L/R frequency responses across all N passes.
  3. Fits once against the averaged result.
  4. Writes per-measurement raw data for transparency.
- Keep the existing independent mode as `--iteration-mode independent` (default for backward compatibility).
- Both modes should write an `iterations_summary.json` that includes per-pass diagnostics.

## Out of scope
- Closed-loop EQ refinement (measure → apply EQ → re-measure). That requires CamillaDSP integration.
- Weighted averaging or outlier rejection (future enhancement).
- GUI changes (the GUI just passes the mode through).

## Acceptance criteria
- `headmatch start --iterations 3 --iteration-mode average` produces one fit from the averaged response.
- Individual raw measurements are preserved in iter_01/, iter_02/, etc.
- The averaged response is written as measurement_left.csv / measurement_right.csv in the parent output dir.
- Confidence scoring runs against the averaged result.
- Existing iteration tests pass. New tests cover the averaging path.

## Suggested files/components
- `headmatch/pipeline.py`
- `headmatch/cli.py` (add --iteration-mode arg)
- `headmatch/contracts.py` (if IterationMode type needed)
- `tests/test_pipeline.py`
- `tests/test_integration_cli.py`
