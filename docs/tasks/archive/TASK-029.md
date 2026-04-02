# TASK-029 — Extract shared fit artifact writing from the pipeline

## Summary
Reduce duplication in the measurement-to-fit pipeline by extracting the shared fit artifact writing flow used by single-run and iterative workflows.

## Context
`pipeline.py` currently repeats the same artifact-writing sequence in `process_single_measurement()` and `iterative_measure_and_fit()`: exporting APO/CamillaDSP files, rendering SVGs, writing reports/summaries, and generating the results guide. That duplication increases drift risk exactly where HeadMatch now needs steady GUI/CLI confidence-presentation polish.

## Scope
- Extract the repeated fit-output writing flow behind a small shared helper.
- Keep output filenames, file contents, and top-level behavior unchanged.
- Keep the current run-summary/report contract stable unless a change is clearly required for the refactor.
- Update or extend tests so the refactor is protected.

## Out of scope
- GUI changes.
- CLI copy changes beyond what is strictly needed.
- New confidence heuristics.
- Changing output filenames or folder structure.

## Acceptance criteria
- `process_single_measurement()` and `iterative_measure_and_fit()` no longer duplicate the fit artifact writing sequence.
- Existing output artifacts are still produced with the same names and expected contents.
- Full test suite passes.
- The resulting code is simpler to extend for future confidence-presentation work.

## Suggested files/components
- `headmatch/pipeline.py`
- `tests/test_pipeline.py`
- possibly `headmatch/contracts.py` if a lightweight helper type improves clarity
