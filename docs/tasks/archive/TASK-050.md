# TASK-050 — Correct relative clone-target semantics in the backend

## Summary
Fix the backend math so clone-target outputs are handled correctly during fitting, plotting, and reporting instead of being treated as ordinary absolute target curves.

## Context
A likely core bug exists today: `clone-target` generates a relative tonal delta between source and target curves, but the fit pipeline currently appears to treat every target CSV as an absolute target response. That can double-count the source response and produce clearly wrong results when users try to tune headphone A toward headphone B.

## Scope
- Audit the clone-target math end to end.
- Make target semantics explicit in the backend (absolute target vs relative transform).
- Ensure fitting, plotting, target export, and summaries use the correct effective target for the current run.
- Preserve support for ordinary absolute target CSVs.
- Update/add tests to cover the corrected behavior.

## Out of scope
- GUI wizard redesign.
- New DSP features beyond fixing the semantics bug.
- Packaging or release changes.

## Acceptance criteria
- Clone-target outputs are mathematically consistent with how `fit`, `fit-offline`, and `start` consume `--target-csv`.
- Relative clone targets no longer get double-applied as if they were absolute targets.
- Graphs and reported target curves match the effective target actually used for the run.
- Existing absolute target CSV workflows remain valid.
- Full test suite passes.

## Suggested files/components
- `headmatch/targets.py`
- `headmatch/io_utils.py`
- `headmatch/pipeline.py`
- `headmatch/plots.py`
- `tests/test_targets.py`
- `tests/test_pipeline.py`
- `tests/test_integration_cli.py`
- `tests/test_clone_target_examples.py`
